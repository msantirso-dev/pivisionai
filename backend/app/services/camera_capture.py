"""Unified camera frame capture: Dahua HTTP API first, RTSP fallback."""

import logging
from typing import Optional, Tuple
from uuid import UUID

from app.core.security import decrypt_camera_password
from app.services.dahua_service import dahua_api_service
from app.services.rtsp_service import resolve_camera_rtsp_urls, rtsp_service

logger = logging.getLogger(__name__)


def capture_live_frame(camera) -> Tuple[Optional[bytes], int, int, str]:
    """
    Capture a JPEG frame from a camera.
    Returns (jpeg_bytes, width, height, source).
    source: 'dahua_http' | 'rtsp' | ''
    """
    password = decrypt_camera_password(camera.password_encrypted)
    api_port = getattr(camera, "dahua_api_port", None) or 80

    if camera.brand.lower() == "dahua":
        result = dahua_api_service.capture_snapshot_sync(
            camera.ip_address,
            api_port,
            camera.username,
            password,
            camera.channel,
        )
        if result:
            jpeg, w, h = result
            logger.debug("Dahua HTTP snapshot OK for %s", camera.ip_address)
            return jpeg, w, h, "dahua_http"

        logger.warning("Dahua HTTP snapshot failed for %s, trying RTSP", camera.ip_address)

    rtsp_main, _ = resolve_camera_rtsp_urls(camera)
    result = rtsp_service.capture_snapshot_bytes(rtsp_main)
    if result:
        jpeg, w, h = result
        return jpeg, w, h, "rtsp"

    return None, 0, 0, ""


def test_camera_connection(camera) -> Tuple[bool, str, Optional[float], Optional[str], str]:
    """Test camera connectivity. Returns (success, message, latency_ms, resolution, method)."""
    import time

    password = decrypt_camera_password(camera.password_encrypted)
    api_port = getattr(camera, "dahua_api_port", None) or 80

    if camera.brand.lower() == "dahua":
        start = time.time()
        result = dahua_api_service.capture_snapshot_sync(
            camera.ip_address, api_port, camera.username, password, camera.channel
        )
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
    Prefers Dahua HTTP snapshot (fast/reliable), falls back to RTSP.
    Returns (frame, width, height, source) or (None, 0, 0, '').
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

    rtsp_main, rtsp_sub = resolve_camera_rtsp_urls(camera)
    from app.config import get_settings

    settings = get_settings()
    rtsp_url = rtsp_sub if settings.use_substream_for_ai and rtsp_sub else rtsp_main
    frame = rtsp_service.read_frame(rtsp_url)
    if frame is None:
        return None, 0, 0, ""

    fh, fw = frame.shape[:2]
    return frame, fw, fh, "rtsp"
