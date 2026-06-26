"""Camera DB helpers — short sessions to avoid pool exhaustion during RTSP/HTTP capture."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import Camera, CameraStatus


async def get_camera(camera_id: UUID) -> Optional[Camera]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Camera).where(Camera.id == camera_id, Camera.is_active == True))
        camera = result.scalar_one_or_none()
        if camera:
            await session.refresh(camera)
            session.expunge(camera)
        return camera


async def update_camera_status(camera_id: UUID, status: CameraStatus, online: bool = False) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Camera).where(Camera.id == camera_id))
        camera = result.scalar_one_or_none()
        if not camera:
            return
        camera.status = status
        if online:
            camera.last_seen_at = datetime.now(timezone.utc)
        await session.commit()
