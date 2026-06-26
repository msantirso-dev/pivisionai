"""Correlated IVS + AI events API."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import CorrelatedEvent, DahuaEvent, Event, User

router = APIRouter(prefix="/correlations", tags=["Correlations"])


class CorrelationResponse(BaseModel):
    id: UUID
    dahua_event_id: UUID
    ai_event_id: UUID
    correlation_score: float
    ai_confirmed: bool
    discarded: bool
    dahua_type: Optional[str] = None
    ai_event_type: Optional[str] = None
    object_class: Optional[str] = None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[CorrelationResponse])
async def list_correlations(
    camera_id: Optional[UUID] = None,
    ai_confirmed: Optional[bool] = None,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(CorrelatedEvent)
        .join(DahuaEvent, CorrelatedEvent.dahua_event_id == DahuaEvent.id)
        .join(Event, CorrelatedEvent.ai_event_id == Event.id)
        .order_by(CorrelatedEvent.created_at.desc())
        .limit(limit)
    )
    if camera_id:
        query = query.where(DahuaEvent.camera_id == camera_id)
    if ai_confirmed is not None:
        query = query.where(CorrelatedEvent.ai_confirmed == ai_confirmed)

    result = await db.execute(query)
    correlations = result.scalars().all()

    responses = []
    for corr in correlations:
        dahua = await db.get(DahuaEvent, corr.dahua_event_id)
        ai_evt = await db.get(Event, corr.ai_event_id)
        responses.append(
            CorrelationResponse(
                id=corr.id,
                dahua_event_id=corr.dahua_event_id,
                ai_event_id=corr.ai_event_id,
                correlation_score=corr.correlation_score,
                ai_confirmed=corr.ai_confirmed,
                discarded=corr.discarded,
                dahua_type=dahua.event_type if dahua else None,
                ai_event_type=ai_evt.event_type if ai_evt else None,
                object_class=ai_evt.object_class if ai_evt else None,
            )
        )
    return responses
