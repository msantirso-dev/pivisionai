"""Dahua cloud connector via Lechange / Imou Open API (乐橙云)."""

import hashlib
import logging
import time
import uuid
from typing import Any, Dict, Optional, Tuple

import cv2
import httpx
import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)


class DahuaCloudService:
    """Access Dahua/Imou devices through the cloud using device serial number."""

    def __init__(self) -> None:
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def is_configured(self) -> bool:
        settings = get_settings()
        return bool(settings.dahua_cloud_app_id and settings.dahua_cloud_app_secret)

    @staticmethod
    def channel_to_cloud_id(channel: int) -> str:
        """Lechange channelId is 0-based."""
        return str(max(0, int(channel) - 1))

    def _compute_sign(self, ts: int, nonce: str) -> str:
        settings = get_settings()
        raw = f"time:{ts},nonce:{nonce},appSecret:{settings.dahua_cloud_app_secret}"
        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    def _api_url(self, method: str) -> str:
        settings = get_settings()
        base = settings.dahua_cloud_api_base.rstrip("/")
        return f"{base}/{method}"

    def _post(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        settings = get_settings()
        if not self.is_configured():
            return {"success": False, "error": "Cloud Dahua no configurado (DAHUA_CLOUD_APP_ID/SECRET)"}

        ts = int(time.time())
        nonce = str(uuid.uuid4())
        payload = {
            "system": {
                "ver": "1.0",
                "appId": settings.dahua_cloud_app_id,
                "sign": self._compute_sign(ts, nonce),
                "time": ts,
                "nonce": nonce,
            },
            "id": str(uuid.uuid4()),
            "params": params or {},
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(self._api_url(method), json=payload)
                response.raise_for_status()
                body = response.json()
        except Exception as exc:
            logger.error("Dahua cloud API %s failed: %s", method, exc)
            return {"success": False, "error": str(exc)}

        result = body.get("result") or {}
        code = str(result.get("code", ""))
        if code != "0":
            return {
                "success": False,
                "error": result.get("msg") or f"API error {code}",
                "code": code,
            }

        return {"success": True, "data": result.get("data") or {}}

    def get_access_token(self, force_refresh: bool = False) -> Optional[str]:
        now = time.time()
        if not force_refresh and self._access_token and now < self._token_expires_at - 60:
            return self._access_token

        response = self._post("accessToken")
        if not response.get("success"):
            logger.warning("Dahua cloud accessToken failed: %s", response.get("error"))
            return None

        data = response.get("data") or {}
        token = data.get("accessToken")
        expire = int(data.get("expireTime") or 3600)
        if not token:
            return None

        self._access_token = token
        self._token_expires_at = now + expire
        return token

    def bind_device(self, device_serial: str, device_code: str) -> Dict[str, Any]:
        """Bind device to the cloud app account (idempotent if already bound)."""
        token = self.get_access_token()
        if not token:
            return {"success": False, "error": "No se pudo obtener accessToken de la nube"}

        check = self._post(
            "checkDeviceBindOrNot",
            {"token": token, "deviceId": device_serial},
        )
        if check.get("success"):
            data = check.get("data") or {}
            if data.get("isMine"):
                return {"success": True, "message": "Dispositivo ya vinculado a la cuenta cloud"}

        bind = self._post(
            "bindDevice",
            {"token": token, "deviceId": device_serial, "code": device_code},
        )
        if bind.get("success"):
            return {"success": True, "message": "Dispositivo vinculado en la nube"}

        error = bind.get("error") or "Error al vincular dispositivo"
        if "已绑定" in error or "already" in error.lower() or bind.get("code") in ("DV1001",):
            return {"success": True, "message": "Dispositivo ya vinculado"}

        return {"success": False, "error": error}

    def capture_snapshot_sync(
        self,
        device_serial: str,
        device_code: str,
        channel: int = 1,
    ) -> Optional[Tuple[bytes, int, int]]:
        """Capture JPEG via cloud setDeviceSnap API."""
        bind_result = self.bind_device(device_serial, device_code)
        if not bind_result.get("success"):
            logger.warning("Cloud bind failed for %s: %s", device_serial, bind_result.get("error"))

        token = self.get_access_token(force_refresh=not bind_result.get("success"))
        if not token:
            return None

        channel_id = self.channel_to_cloud_id(channel)
        snap = self._post(
            "setDeviceSnap",
            {"token": token, "deviceId": device_serial, "channelId": channel_id},
        )
        if not snap.get("success"):
            snap = self._post(
                "setDeviceSnapEnhanced",
                {"token": token, "deviceId": device_serial, "channelId": channel_id},
            )
        if not snap.get("success"):
            logger.warning("Cloud snapshot failed for %s: %s", device_serial, snap.get("error"))
            return None

        url = (snap.get("data") or {}).get("url")
        if not url:
            return None

        try:
            with httpx.Client(timeout=20.0, follow_redirects=True) as client:
                img_resp = client.get(url)
                img_resp.raise_for_status()
                content = img_resp.content
        except Exception as exc:
            logger.error("Cloud snapshot download failed: %s", exc)
            return None

        if len(content) < 100:
            return None

        arr = np.frombuffer(content, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return None

        h, w = img.shape[:2]
        return content, w, h

    def test_connection(
        self,
        device_serial: str,
        device_code: str,
        channel: int = 1,
    ) -> Dict[str, Any]:
        start = time.time()
        if not self.is_configured():
            return {"success": False, "message": "Configure DAHUA_CLOUD_APP_ID y DAHUA_CLOUD_APP_SECRET en .env"}

        bind = self.bind_device(device_serial, device_code)
        if not bind.get("success"):
            return {"success": False, "message": bind.get("error") or "Error al vincular en la nube"}

        result = self.capture_snapshot_sync(device_serial, device_code, channel)
        if not result:
            return {
                "success": False,
                "message": "No se pudo capturar imagen desde la nube. Verifique serial y contraseña.",
            }

        _, w, h = result
        latency = (time.time() - start) * 1000
        return {
            "success": True,
            "message": f"Conexión cloud OK ({bind.get('message', 'vinculado')})",
            "latency_ms": latency,
            "resolution": f"{w}x{h}",
        }


dahua_cloud_service = DahuaCloudService()
