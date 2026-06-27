"""Route camera operations to local LAN or Dahua cloud connector."""

from typing import Optional, Tuple

from app.core.security import decrypt_camera_password
from app.services.dahua_cloud_service import dahua_cloud_service
from app.services.dahua_service import dahua_api_service


def is_cloud_camera(camera) -> bool:
    mode = getattr(camera, "connection_mode", None) or "local"
    return str(mode).lower() == "cloud"


def cloud_serial(camera) -> Optional[str]:
    serial = getattr(camera, "device_serial", None)
    if serial:
        return serial.strip()
    if is_cloud_camera(camera) and camera.ip_address and not _looks_like_ip(camera.ip_address):
        return camera.ip_address.strip()
    return None


def _looks_like_ip(value: str) -> bool:
    parts = value.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return False


def capture_snapshot_sync(camera) -> Optional[Tuple[bytes, int, int]]:
    password = decrypt_camera_password(camera.password_encrypted)

    if is_cloud_camera(camera):
        serial = cloud_serial(camera)
        if not serial:
            return None
        return dahua_cloud_service.capture_snapshot_sync(
            serial,
            password,
            camera.channel,
        )

    api_port = getattr(camera, "dahua_api_port", None) or 80
    if camera.brand.lower() == "dahua":
        return dahua_api_service.capture_snapshot_sync(
            camera.ip_address,
            api_port,
            camera.username,
            password,
            camera.channel,
        )
    return None
