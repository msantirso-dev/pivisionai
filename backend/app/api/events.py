"""Events API routes."""

import os
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import Event, EventScore, EventSeverity, EventSnapshot, EventStatus, OperatorAction, User
from app.schemas import EventResponse, EventSearchParams, EventUpdate, OperatorActionCreate

router = APIRouter(prefix="/events", tags=["Events"])


def _snapshot_url_for_event(event: Event) -> Optional[str]:
    if not event.snapshots:
        return None
    filename = os.path.basename(event.snapshots[0].file_path)
    return f"/api/v1/evidence/snapshots/{filename}"


def _event_to_response(event: Event) -> EventResponse:
    return EventResponse.model_validate(event).model_copy(
        update={"snapshot_url": _snapshot_url_for_event(event)}
    )


@router.get("", response_model=list[EventResponse])
async def list_events(
    camera_id: Optional[UUID] = None,
    object_class: Optional[str] = None,
    severity: Optional[EventSeverity] = None,
    status_filter: Optional[EventStatus] = Query(None, alias="status"),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conditions = []
    if camera_id:
        conditions.append(Event.camera_id == camera_id)
    if object_class:
        conditions.append(Event.object_class == object_class)
    if severity:
        conditions.append(Event.severity == severity)
    if status_filter:
        conditions.append(Event.status == status_filter)
    if date_from:
        conditions.append(Event.occurred_at >= date_from)
    if date_to:
        conditions.append(Event.occurred_at <= date_to)

    query = (
        select(Event)
        .options(selectinload(Event.snapshots))
        .order_by(Event.occurred_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if conditions:
        query = query.where(and_(*conditions))

    result = await db.execute(query)
    return [_event_to_response(event) for event in result.scalars().all()]


@router.get("/search", response_model=list[EventResponse])
async def search_events(
    params: EventSearchParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await list_events(
        camera_id=params.camera_id,
        object_class=params.object_class,
        severity=params.severity,
        status_filter=params.status,
        date_from=params.date_from,
        date_to=params.date_to,
        limit=params.limit,
        offset=params.offset,
        db=db,
        current_user=current_user,
    )


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Event).options(selectinload(Event.snapshots)).where(Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return _event_to_response(event)


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: UUID,
    data: EventUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    previous_status = event.status.value if hasattr(event.status, "value") else event.status

    if data.status:
        event.status = data.status
    if data.assigned_to:
        event.assigned_to = data.assigned_to

    if data.status or data.comment:
        action = OperatorAction(
            event_id=event.id,
            operator_id=current_user.id,
            action="status_change" if data.status else "comment",
            previous_status=previous_status,
            new_status=data.status.value if data.status else None,
            comment=data.comment,
        )
        db.add(action)

    await db.flush()
    result = await db.execute(
        select(Event).options(selectinload(Event.snapshots)).where(Event.id == event.id)
    )
    event = result.scalar_one()
    return _event_to_response(event)


@router.post("/{event_id}/actions", status_code=status.HTTP_201_CREATED)
async def add_operator_action(
    event_id: UUID,
    data: OperatorActionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    previous_status = event.status.value if hasattr(event.status, "value") else event.status
    if data.new_status:
        event.status = data.new_status

    action = OperatorAction(
        event_id=event.id,
        operator_id=current_user.id,
        action=data.action,
        previous_status=previous_status,
        new_status=data.new_status.value if data.new_status else None,
        comment=data.comment,
    )
    db.add(action)
    await db.flush()
    return {"status": "ok", "action_id": str(action.id)}
