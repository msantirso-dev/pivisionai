"""LLM vision configuration and analysis API."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.database import get_db
from app.models import Camera, DetectionRule, Event, EventSnapshot, User, UserRole
from app.services.event_review import build_review_description
from app.services.llm_config import load_llm_config, public_config, save_llm_config
from app.services.llm_service import llm_vision_service
from app.services.llm_usage import get_llm_usage_stats

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
    openrouter_api_key: str | None = None
    openrouter_model: str | None = None
    openrouter_base_url: str | None = None
    openrouter_site_url: str | None = None
    openrouter_app_name: str | None = None
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
    usage: dict | None = None


class LLMUsageStats(BaseModel):
    total: dict
    today: dict
    by_provider: dict


@router.get("/usage", response_model=LLMUsageStats)
async def get_llm_usage(
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPERVISOR])),
):
    return get_llm_usage_stats()


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

    meta = event.metadata_ or {}
    context_description = meta.get("context_description") or ""
    rule_name = meta.get("rule_name")
    if event.rule_id and not context_description:
        rule_result = await db.execute(select(DetectionRule).where(DetectionRule.id == event.rule_id))
        rule = rule_result.scalar_one_or_none()
        if rule:
            rule_name = rule_name or rule.name
            context_description = rule.context_description or ""

    cfg = await load_llm_config(db)
    context = {
        "camera_name": camera.name if camera else "",
        "location": camera.location if camera else "",
        "event_type": event.event_type,
        "object_class": event.object_class,
        "description": event.description,
        "rule_name": rule_name,
        "context_description": context_description,
        "source": "event_manual",
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
        "usage": analysis.get("usage"),
    }
    event.metadata_ = meta
    parsed = analysis.get("parsed") or {}
    review_text = build_review_description(parsed, event.description or "")
    if review_text:
        event.description = review_text
    await db.commit()
    await db.refresh(event)

    import os
    from app.services.websocket_manager import ws_manager

    snapshot_url = f"/api/v1/evidence/snapshots/{os.path.basename(snapshot.file_path)}"
    await ws_manager.send_event(
        {
            "id": str(event.id),
            "camera_id": str(event.camera_id),
            "event_type": event.event_type,
            "severity": event.severity.value if hasattr(event.severity, "value") else event.severity,
            "object_class": event.object_class,
            "description": event.description,
            "confidence": event.confidence,
            "occurred_at": event.occurred_at.isoformat(),
            "metadata": event.metadata_,
            "snapshot_url": snapshot_url,
            "llm_updated": True,
        }
    )

    return LLMAnalysisResponse(
        success=True,
        provider=analysis.get("provider"),
        analysis=analysis.get("analysis"),
        parsed=analysis.get("parsed"),
        usage=analysis.get("usage"),
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
        {"camera_name": camera.name, "location": camera.location, "capture_source": source, "source": "camera_test"},
        cfg,
    )
    if not analysis.get("success"):
        return LLMAnalysisResponse(success=False, error=analysis.get("error"))

    return LLMAnalysisResponse(
        success=True,
        provider=analysis.get("provider"),
        analysis=analysis.get("analysis"),
        parsed=analysis.get("parsed"),
        usage=analysis.get("usage"),
    )
