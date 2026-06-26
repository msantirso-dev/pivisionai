"""RTSP camera service with OpenCV."""

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional, Tuple
from urllib.parse import quote
from uuid import UUID

import cv2
import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# RTSP over TCP + timeout 8s (microseconds) — más estable con Dahua
os.environ.setdefault(
    "OPENCV_FFMPEG_CAPTURE_OPTIONS",
    f"rtsp_transport;tcp|stimeout;{settings.rtsp_timeout * 1000000}",
)

_executor = ThreadPoolExecutor(max_workers=8)


def build_dahua_rtsp_url(
    ip: str,
    port: int,
    username: str,
    password: str,
    channel: int = 1,
    subtype: int = 0,
) -> str:
    """Build Dahua RTSP URL with URL-encoded credentials."""
    user = quote(username, safe="")
    pwd = quote(password, safe="")
    return f"rtsp://{user}:{pwd}@{ip}:{port}/cam/realmonitor?channel={channel}&subtype={subtype}"


def resolve_camera_rtsp_urls(camera) -> Tuple[str, Optional[str]]:
    """Rebuild RTSP URLs from stored credentials (handles special chars in password)."""
    from app.core.security import decrypt_camera_password

    password = decrypt_camera_password(camera.password_encrypted)
    if camera.brand.lower() == "dahua":
        main = build_dahua_rtsp_url(
            camera.ip_address, camera.port, camera.username, password, camera.channel, subtype=0
        )
        sub = build_dahua_rtsp_url(
            camera.ip_address, camera.port, camera.username, password, camera.channel, subtype=1
        )
        return main, sub
    return camera.rtsp_main, camera.rtsp_sub


class RTSPService:
    def __init__(self):
        os.makedirs(settings.snapshots_path, exist_ok=True)

    def _open_capture(self, rtsp_url: str) -> cv2.VideoCapture:
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, settings.rtsp_timeout * 1000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, settings.rtsp_timeout * 1000)
        return cap

    def test_connection(self, rtsp_url: str) -> Tuple[bool, str, Optional[float], Optional[str]]:
        cap = None
        try:
            start = time.time()
            cap = self._open_capture(rtsp_url)

            if not cap.isOpened():
                return False, "No se pudo abrir el stream RTSP. Verifique IP, puerto y credenciales.", None, None

            ret, frame = cap.read()
            latency = (time.time() - start) * 1000

            if not ret or frame is None:
                return False, "Stream abierto pero sin frames. Pruebe con rtsp_transport=tcp.", latency, None

            h, w = frame.shape[:2]
            return True, "Conexión RTSP exitosa", latency, f"{w}x{h}"
        except Exception as e:
            logger.error("RTSP test failed: %s", e)
            return False, f"Error RTSP: {e}", None, None
        finally:
            if cap:
                cap.release()

    def capture_snapshot(
        self,
        rtsp_url: str,
        camera_id: UUID,
    ) -> Optional[Tuple[str, int, int]]:
        cap = None
        try:
            cap = self._open_capture(rtsp_url)

            if not cap.isOpened():
                logger.warning("Cannot open RTSP for camera %s", camera_id)
                return None

            ret, frame = cap.read()
            if not ret or frame is None:
                logger.warning("No frame from camera %s", camera_id)
                return None

            h, w = frame.shape[:2]
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"{camera_id}_{timestamp}.jpg"
            filepath = os.path.join(settings.snapshots_path, filename)

            cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            return filepath, w, h
        except Exception as e:
            logger.error("Snapshot capture failed for %s: %s", camera_id, e)
            return None
        finally:
            if cap:
                cap.release()

    def capture_snapshot_bytes(self, rtsp_url: str) -> Optional[Tuple[bytes, int, int]]:
        """Capture frame and return JPEG bytes (for live preview)."""
        cap = None
        try:
            cap = self._open_capture(rtsp_url)
            if not cap.isOpened():
                return None
            ret, frame = cap.read()
            if not ret or frame is None:
                return None
            h, w = frame.shape[:2]
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ok:
                return None
            return buf.tobytes(), w, h
        except Exception as e:
            logger.error("Snapshot bytes failed: %s", e)
            return None
        finally:
            if cap:
                cap.release()

    def read_frame(self, rtsp_url: str) -> Optional[np.ndarray]:
        cap = None
        try:
            cap = self._open_capture(rtsp_url)
            if not cap.isOpened():
                return None
            ret, frame = cap.read()
            return frame if ret else None
        except Exception as e:
            logger.error("Frame read failed: %s", e)
            return None
        finally:
            if cap:
                cap.release()

    def run_sync(self, func, *args):
        """Run blocking RTSP op in thread pool."""
        return _executor.submit(func, *args).result(timeout=settings.rtsp_timeout + 5)


rtsp_service = RTSPService()
