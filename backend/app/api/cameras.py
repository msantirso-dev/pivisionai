"""Camera management API routes."""

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.dependencies import get_current_user, require_roles
from app.core.security import decrypt_camera_password, encrypt_camera_password
from app.database import get_db
from app.models import AuditLog, Camera, CameraStatus, User, UserRole
from app.schemas import CameraCreate, CameraResponse, CameraTestResult, CameraUpdate, SnapshotResponse
from app.services.camera_capture import capture_live_frame, test_camera_connection
from app.services.camera_db import get_camera as load_camera, update_camera_status
from app.services.snapshot_cache import get_cached, set_cached
from app.services.rtsp_service import build_dahua_rtsp_url, resolve_camera_rtsp_urls, rtsp_service
from app.workers.tasks import start_camera_analysis

router = APIRouter(prefix="/cameras", tags=["Cameras"])
settings = get_settings()


def _camera_to_response(camera: Camera) -> CameraResponse:
    return CameraResponse(
        id=camera.id,
        name=camera.name,
        location=camera.location,
        ip_address=camera.ip_address,
        port=camera.port,
        brand=camera.brand,
        model=camera.model,
        rtsp_main=f"rtsp://{camera.username}:***@{camera.ip_address}:{camera.port}/...",
        rtsp_sub=f"rtsp://{camera.username}:***@{camera.ip_address}:{camera.port}/.../subtype=1" if camera.rtsp_sub else None,
        channel=camera.channel,
        zone=camera.zone,
        status=camera.status.value if hasattr(camera.status, "value") else camera.status,
        ai_enabled=camera.ai_enabled,
        ai_fps=camera.ai_fps,
        ai_confidence=camera.ai_confidence,
        dahua_api_enabled=camera.dahua_api_enabled,
        is_active=camera.is_active,
        last_seen_at=camera.last_seen_at,
        created_at=camera.created_at,
    )


def _sync_rtsp_urls(camera: Camera) -> None:
    """Persist correctly encoded RTSP URLs from stored credentials."""
    main, sub = resolve_camera_rtsp_urls(camera)
    camera.rtsp_main = main
    camera.rtsp_sub = sub


@router.get("", response_model=list[CameraResponse])
async def list_cameras(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Camera).where(Camera.is_active == True).order_by(Camera.name))
    return [_camera_to_response(c) for c in result.scalars().all()]


@router.post("", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
async def create_camera(
    data: CameraCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPERVISOR])),
):
    rtsp_main = data.rtsp_main
    rtsp_sub = data.rtsp_sub

    if not rtsp_main and data.brand.lower() == "dahua":
        rtsp_main = build_dahua_rtsp_url(
            data.ip_address, data.port, data.username, data.password, data.channel, subtype=0
        )
        rtsp_sub = build_dahua_rtsp_url(
            data.ip_address, data.port, data.username, data.password, data.channel, subtype=1
        )

    camera = Camera(
        name=data.name,
        location=data.location,
        ip_address=data.ip_address,
        port=data.port,
        username=data.username,
        password_encrypted=encrypt_camera_password(data.password),
        brand=data.brand,
        model=data.model,
        rtsp_main=rtsp_main,
        rtsp_sub=rtsp_sub,
        onvif_url=data.onvif_url,
        channel=data.channel,
        site_id=data.site_id,
        group_id=data.group_id,
        zone=data.zone,
        ai_enabled=data.ai_enabled,
        ai_fps=data.ai_fps,
        ai_confidence=data.ai_confidence,
        dahua_api_enabled=data.dahua_api_enabled,
        dahua_api_port=data.dahua_api_port,
    )
    db.add(camera)
    await db.flush()
    _sync_rtsp_urls(camera)
    await db.flush()
    await db.refresh(camera)

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="create",
            resource_type="camera",
            resource_id=str(camera.id),
            details={"name": camera.name},
        )
    )

    if camera.ai_enabled:
        start_camera_analysis.delay(str(camera.id))

    return _camera_to_response(camera)


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(
    camera_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    return _camera_to_response(camera)


@router.patch("/{camera_id}", response_model=CameraResponse)
async def update_camera(
    camera_id: UUID,
    data: CameraUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPERVISOR])),
):
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")

    update_data = data.model_dump(exclude_unset=True)
    if "password" in update_data:
        camera.password_encrypted = encrypt_camera_password(update_data.pop("password"))

    for key, value in update_data.items():
        setattr(camera, key, value)

    _sync_rtsp_urls(camera)
    await db.flush()
    await db.refresh(camera)
    return _camera_to_response(camera)


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(
    camera_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN])),
):
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    camera.is_active = False
    await db.flush()


@router.post("/{camera_id}/test", response_model=CameraTestResult)
async def test_camera(
    camera_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    camera = await load_camera(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")

    try:
        success, message, latency, resolution, method = await asyncio.to_thread(
            test_camera_connection, camera
        )
        if method == "dahua_http":
            message = f"{message} (API Dahua HTTP)"
    except Exception as e:
        success, message, latency, resolution = False, str(e), None, None

    await update_camera_status(
        camera_id,
        CameraStatus.ONLINE if success else CameraStatus.ERROR,
        online=success,
    )
    return CameraTestResult(success=success, message=message, latency_ms=latency, resolution=resolution)


@router.get("/{camera_id}/snapshot/live")
async def live_snapshot(
    camera_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """Return JPEG via Dahua HTTP API (fast) or RTSP fallback. Cached 4s."""
    cached = get_cached(camera_id)
    if cached:
        jpeg_bytes, width, height, source = cached
        return Response(
            content=jpeg_bytes,
            media_type="image/jpeg",
            headers={
                "X-Image-Width": str(width),
                "X-Image-Height": str(height),
                "X-Capture-Source": source,
                "X-Cache": "hit",
            },
        )

    camera = await load_camera(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")

    try:
        jpeg_bytes, width, height, source = await asyncio.to_thread(capture_live_frame, camera)
    except Exception as e:
        raise HTTPException(status_code=504, detail=f"Error al capturar: {e}")

    if not jpeg_bytes:
        raise HTTPException(
            status_code=503,
            detail="No se pudo obtener imagen. Verifique IP, credenciales y puerto HTTP (80) de la cámara Dahua.",
        )

    set_cached(camera_id, jpeg_bytes, width, height, source)
    await update_camera_status(camera_id, CameraStatus.ONLINE, online=True)

    return Response(
        content=jpeg_bytes,
        media_type="image/jpeg",
        headers={
            "X-Image-Width": str(width),
            "X-Image-Height": str(height),
            "X-Capture-Source": source,
            "X-Cache": "miss",
        },
    )


@router.post("/{camera_id}/snapshot", response_model=SnapshotResponse)
async def capture_snapshot(
    camera_id: UUID,
    current_user: User = Depends(get_current_user),
):
    camera = await load_camera(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")

    try:
        jpeg_bytes, width, height, source = await asyncio.to_thread(capture_live_frame, camera)
    except Exception as e:
        await update_camera_status(camera_id, CameraStatus.ERROR)
        raise HTTPException(status_code=504, detail=f"Timeout: {e}")

    if not jpeg_bytes:
        raise HTTPException(status_code=500, detail="No se pudo capturar snapshot")

    import os
    from datetime import datetime, timezone

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{camera_id}_{timestamp}.jpg"
    filepath = os.path.join(settings.snapshots_path, filename)
    os.makedirs(settings.snapshots_path, exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(jpeg_bytes)

    await update_camera_status(camera_id, CameraStatus.ONLINE, online=True)

    filename_only = filepath.split("/")[-1]
    return SnapshotResponse(
        camera_id=camera.id,
        file_path=filepath,
        url=f"/api/v1/evidence/snapshots/{filename_only}",
        width=width,
        height=height,
        captured_at=datetime.now(timezone.utc),
    )
