"""Unified camera frame capture: cloud API, local Dahua HTTP, RTSP fallback."""

import logging
from typing import Optional, Tuple

from app.core.security import decrypt_camera_password
from app.services.camera_connector import capture_snapshot_sync, is_cloud_camera
from app.services.dahua_cloud_service import dahua_cloud_service
from app.services.rtsp_service import resolve_camera_rtsp_urls, rtsp_service

logger = logging.getLogger(__name__)


def capture_live_frame(camera) -> Tuple[Optional[bytes], int, int, str]:
    """
    Capture a JPEG frame from a camera.
    Returns (jpeg_bytes, width, height, source).
    source: 'dahua_cloud' | 'dahua_http' | 'rtsp' | ''
    """
    if is_cloud_camera(camera):
        result = capture_snapshot_sync(camera)
        if result:
            jpeg, w, h = result
            return jpeg, w, h, "dahua_cloud"
        return None, 0, 0, ""

    password = decrypt_camera_password(camera.password_encrypted)
    result = capture_snapshot_sync(camera)
    if result:
        jpeg, w, h = result
        logger.debug("Dahua HTTP snapshot OK for %s", camera.ip_address)
        return jpeg, w, h, "dahua_http"

    if camera.brand.lower() == "dahua":
        logger.warning("Dahua HTTP snapshot failed for %s, trying RTSP", camera.ip_address)

    rtsp_main, _ = resolve_camera_rtsp_urls(camera)
    if not rtsp_main:
        return None, 0, 0, ""

    result = rtsp_service.capture_snapshot_bytes(rtsp_main)
    if result:
        jpeg, w, h = result
        return jpeg, w, h, "rtsp"

    return None, 0, 0, ""


def test_camera_connection(camera) -> Tuple[bool, str, Optional[float], Optional[str], str]:
    """Test camera connectivity. Returns (success, message, latency_ms, resolution, method)."""
    import time

    if is_cloud_camera(camera):
        from app.services.camera_connector import cloud_serial

        serial = cloud_serial(camera)
        if not serial:
            return False, "Falta número de serie del dispositivo", None, None, "dahua_cloud"
        if not dahua_cloud_service.is_configured():
            return (
                False,
                "Cloud Dahua no configurado (DAHUA_CLOUD_APP_ID/SECRET en .env)",
                None,
                None,
                "dahua_cloud",
            )
        password = decrypt_camera_password(camera.password_encrypted)
        result = dahua_cloud_service.test_connection(serial, password, camera.channel)
        if result.get("success"):
            return (
                True,
                result.get("message", "Conexión cloud OK"),
                result.get("latency_ms"),
                result.get("resolution"),
                "dahua_cloud",
            )
        return False, result.get("message", "Error cloud"), None, None, "dahua_cloud"

    password = decrypt_camera_password(camera.password_encrypted)
    start = time.time()
    result = capture_snapshot_sync(camera)
    if result:
        _, w, h = result
        latency = (time.time() - start) * 1000
        return True, "Conexión Dahua API exitosa", latency, f"{w}x{h}", "dahua_http"

    rtsp_main, _ = resolve_camera_rtsp_urls(camera)
    success, message, latency, resolution = rtsp_service.test_connection(rtsp_main)
    return success, message, latency, resolution, "rtsp"


def capture_frame_np(camera):
    """
    Capture a BGR numpy frame for AI analysis.
    Prefers HTTP/cloud snapshot, falls back to RTSP for local cameras.
    """
    import cv2
    import numpy as np

    jpeg, w, h, source = capture_live_frame(camera)
    if jpeg:
        arr = np.frombuffer(jpeg, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is not None:
            fh, fw = frame.shape[:2]
            return frame, fw, fh, source

    if is_cloud_camera(camera):
        return None, 0, 0, ""

    rtsp_main, rtsp_sub = resolve_camera_rtsp_urls(camera)
    from app.config import get_settings

    settings = get_settings()
    rtsp_url = rtsp_sub if settings.use_substream_for_ai and rtsp_sub else rtsp_main
    if not rtsp_url:
        return None, 0, 0, ""

    frame = rtsp_service.read_frame(rtsp_url)
    if frame is None:
        return None, 0, 0, ""

    fh, fw = frame.shape[:2]
    return frame, fw, fh, "rtsp"
