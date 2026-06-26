"""LLM vision configuration and analysis API."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.database import get_db
from app.models import Camera, Event, EventSnapshot, User, UserRole
from app.services.llm_config import load_llm_config, public_config, save_llm_config
from app.services.llm_service import llm_vision_service
from app.workers.tasks import analyze_event_with_llm

router = APIRouter(prefix="/ai/llm", tags=["LLM Vision"])


class LLMConfigUpdate(BaseModel):
    enabled: bool | None = None
    provider: str | None = None
    analyze_on_event: bool | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    openai_api_key: str | None = None
    openai_model: str | None = None
    openai_base_url: str | None = None
    max_tokens: int | None = None
    system_prompt: str | None = None


class LLMTestResponse(BaseModel):
    success: bool
    message: str
    model_available: bool | None = None


class LLMAnalysisResponse(BaseModel):
    success: bool
    provider: str | None = None
    analysis: str | None = None
    parsed: dict | None = None
    error: str | None = None


@router.get("/config")
async def get_llm_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPERVISOR])),
):
    cfg = await load_llm_config(db)
    return public_config(cfg)


@router.put("/config")
async def update_llm_config(
    data: LLMConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN])),
):
    updates = data.model_dump(exclude_unset=True)
    cfg = await save_llm_config(db, updates)
    return public_config(cfg)


@router.post("/test", response_model=LLMTestResponse)
async def test_llm_connection(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPERVISOR])),
):
    cfg = await load_llm_config(db)
    result = await llm_vision_service.test_connection(cfg)
    return LLMTestResponse(
        success=result.get("success", False),
        message=result.get("message", ""),
        model_available=result.get("model_available"),
    )


@router.post("/events/{event_id}/analyze", response_model=LLMAnalysisResponse)
async def analyze_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    snap_result = await db.execute(
        select(EventSnapshot).where(EventSnapshot.event_id == event_id).order_by(EventSnapshot.created_at.desc())
    )
    snapshot = snap_result.scalars().first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="El evento no tiene snapshot")

    cam_result = await db.execute(select(Camera).where(Camera.id == event.camera_id))
    camera = cam_result.scalar_one_or_none()

    cfg = await load_llm_config(db)
    context = {
        "camera_name": camera.name if camera else "",
        "location": camera.location if camera else "",
        "event_type": event.event_type,
        "object_class": event.object_class,
        "description": event.description,
    }

    analysis = await llm_vision_service.analyze_image_file(snapshot.file_path, context, cfg)
    if not analysis.get("success"):
        return LLMAnalysisResponse(success=False, error=analysis.get("error"))

    meta = dict(event.metadata_ or {})
    meta["llm_analysis"] = {
        "provider": analysis.get("provider"),
        "model": analysis.get("model"),
        "text": analysis.get("analysis"),
        "parsed": analysis.get("parsed"),
    }
    event.metadata_ = meta
    if analysis.get("parsed", {}).get("summary"):
        event.description = analysis["parsed"]["summary"]
    await db.flush()

    return LLMAnalysisResponse(
        success=True,
        provider=analysis.get("provider"),
        analysis=analysis.get("analysis"),
        parsed=analysis.get("parsed"),
    )


@router.post("/analyze-image", response_model=LLMAnalysisResponse)
async def analyze_camera_live(
    camera_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPERVISOR])),
):
    """Analizar imagen en vivo de una cámara con LLM."""
    from app.services.camera_capture import capture_live_frame
    from app.services.camera_db import get_camera
    import asyncio

    camera = await get_camera(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")

    jpeg, w, h, source = await asyncio.to_thread(capture_live_frame, camera)
    if not jpeg:
        raise HTTPException(status_code=503, detail="No se pudo capturar imagen")

    import base64

    cfg = await load_llm_config(db)
    cfg = {**cfg, "enabled": True}
    analysis = await llm_vision_service.analyze_image_base64(
        base64.b64encode(jpeg).decode(),
        {"camera_name": camera.name, "location": camera.location, "capture_source": source},
        cfg,
    )
    if not analysis.get("success"):
        return LLMAnalysisResponse(success=False, error=analysis.get("error"))

    return LLMAnalysisResponse(
        success=True,
        provider=analysis.get("provider"),
        analysis=analysis.get("analysis"),
        parsed=analysis.get("parsed"),
    )
