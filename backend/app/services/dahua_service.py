"""Dahua CGI/HTTP API integration for IVS events."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import cv2
import httpx
import numpy as np

from app.core.security import decrypt_camera_password

logger = logging.getLogger(__name__)

IVS_EVENT_TYPES = {
    "CrossLineDetection": "tripwire",
    "CrossRegionDetection": "intrusion",
    "VideoMotion": "motion_detect",
    "VideoAbnormalDetection": "tamper",
    "VideoLoss": "video_loss",
    "NumberStat": "people_counting",
}


class DahuaAPIService:
    def _auth(self, username: str, password_encrypted: str) -> httpx.DigestAuth:
        password = decrypt_camera_password(password_encrypted)
        return httpx.DigestAuth(username, password)

    async def test_connection(self, ip: str, port: int, username: str, password_encrypted: str) -> Dict:
        url = f"http://{ip}:{port}/cgi-bin/magicBox.cgi?action=getSystemInfo"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, auth=self._auth(username, password_encrypted))
                if response.status_code == 200:
                    return {"success": True, "message": "Conexión Dahua API exitosa"}
                return {"success": False, "message": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def get_ivs_config(self, ip: str, port: int, username: str, password_encrypted: str, channel: int = 1) -> Dict:
        url = f"http://{ip}:{port}/cgi-bin/configManager.cgi?action=getConfig&name=VideoAnalyseRule[{channel - 1}]"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, auth=self._auth(username, password_encrypted))
                if response.status_code == 200:
                    return {"success": True, "config": response.text}
                return {"success": False, "message": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def poll_events(
        self, ip: str, port: int, username: str, password_encrypted: str
    ) -> List[Dict[str, Any]]:
        """Poll Dahua event manager for IVS events."""
        url = f"http://{ip}:{port}/cgi-bin/eventManager.cgi?action=getEventIndexes&code=All"
        events = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, auth=self._auth(username, password_encrypted))
                if response.status_code != 200:
                    return events

                for line in response.text.split("\n"):
                    line = line.strip()
                    if not line or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    if "Code" in key or "action" in key.lower():
                        ivs_type = IVS_EVENT_TYPES.get(value, value)
                        events.append(
                            {
                                "event_type": ivs_type,
                                "ivs_type": value,
                                "raw_payload": {"line": line, "key": key, "value": value},
                                "occurred_at": datetime.now(timezone.utc).isoformat(),
                            }
                        )
        except Exception as e:
            logger.error("Dahua poll failed for %s: %s", ip, e)

        return events

    def capture_snapshot_sync(
        self,
        ip: str,
        port: int,
        username: str,
        password: str,
        channel: int = 1,
    ) -> Optional[Tuple[bytes, int, int]]:
        """
        Capture JPEG via Dahua HTTP API (snapshot.cgi).
        Reuses digest auth session to avoid 401 storms on rapid polling.
        """
        url = f"http://{ip}:{port}/cgi-bin/snapshot.cgi?channel={channel}"
        auth = httpx.DigestAuth(username, password)
        try:
            with httpx.Client(timeout=8.0, auth=auth) as client:
                response = client.get(url)
                if response.status_code != 200:
                    logger.warning("Dahua snapshot HTTP %s for %s", response.status_code, ip)
                    return None
                content = response.content
                if len(content) < 100:
                    return None
                arr = np.frombuffer(content, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is None:
                    return None
                h, w = img.shape[:2]
                return content, w, h
        except Exception as e:
            logger.error("Dahua snapshot failed for %s: %s", ip, e)
            return None


dahua_api_service = DahuaAPIService()
