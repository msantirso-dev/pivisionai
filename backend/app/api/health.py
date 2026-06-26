"""Health and system monitoring API."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import redis

from app.config import get_settings
from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import Camera, CameraStatus, SystemHealthLog, User
from app.schemas import HealthResponse, SystemHealthResponse
from app.services.health_service import health_service

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    db_status = "ok"
    redis_status = "ok"

    try:
        await db.execute(select(1))
    except Exception:
        db_status = "error"

    try:
        r = redis.from_url(settings.redis_url)
        r.ping()
    except Exception:
        redis_status = "error"

    overall = "healthy" if db_status == "ok" and redis_status == "ok" else "degraded"

    return HealthResponse(
        status=overall,
        database=db_status,
        redis=redis_status,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/system/health", response_model=SystemHealthResponse)
async def system_health(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    metrics = health_service.get_system_metrics()
    cameras = await health_service.get_camera_health(db)

    online = sum(1 for c in cameras if c["status"] == "online")
    offline = sum(1 for c in cameras if c["status"] == "offline")
    errors = sum(1 for c in cameras if c["status"] == "error")

    queue_size = 0
    active_workers = 0
    try:
        r = redis.from_url(settings.celery_broker_url)
        queue_size = r.llen("ai") + r.llen("default")
        active_workers = len(r.smembers("celery")) if r.exists("celery") else 0
    except Exception:
        pass

    health_log = SystemHealthLog(
        cpu_percent=metrics["cpu_percent"],
        ram_percent=metrics["ram_percent"],
        gpu_percent=metrics.get("gpu_percent"),
        vram_percent=metrics.get("vram_percent"),
        disk_percent=metrics["disk_percent"],
        network_mbps=metrics.get("network_mbps"),
        queue_size=queue_size,
        active_workers=active_workers,
        online_cameras=online,
        offline_cameras=offline,
        error_cameras=errors,
        degraded_mode=metrics["degraded_mode"],
    )
    db.add(health_log)
    await db.flush()

    return SystemHealthResponse(
        cpu_percent=metrics["cpu_percent"],
        ram_percent=metrics["ram_percent"],
        gpu_percent=metrics.get("gpu_percent"),
        vram_percent=metrics.get("vram_percent"),
        disk_percent=metrics["disk_percent"],
        queue_size=queue_size,
        active_workers=active_workers,
        online_cameras=online,
        offline_cameras=offline,
        error_cameras=errors,
        degraded_mode=metrics["degraded_mode"],
        cameras=cameras,
    )
