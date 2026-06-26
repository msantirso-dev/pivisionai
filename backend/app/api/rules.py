"""Detection rules and schedules API."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.database import get_db
from app.models import DetectionRule, Schedule, User, UserRole
from app.schemas import DetectionRuleCreate, DetectionRuleResponse, DetectionRuleUpdate, ScheduleCreate, ScheduleResponse

router = APIRouter(tags=["Rules & Schedules"])


@router.get("/rules", response_model=list[DetectionRuleResponse])
async def list_rules(
    camera_id: UUID = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(DetectionRule).where(DetectionRule.is_active == True)
    if camera_id:
        query = query.where(DetectionRule.camera_id == camera_id)
    result = await db.execute(query.order_by(DetectionRule.name))
    return result.scalars().all()


@router.post("/rules", response_model=DetectionRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    data: DetectionRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPERVISOR])),
):
    rule = DetectionRule(**data.model_dump())
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return rule


@router.get("/rules/{rule_id}", response_model=DetectionRuleResponse)
async def get_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(DetectionRule).where(DetectionRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    return rule


@router.patch("/rules/{rule_id}", response_model=DetectionRuleResponse)
async def update_rule(
    rule_id: UUID,
    data: DetectionRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPERVISOR])),
):
    result = await db.execute(select(DetectionRule).where(DetectionRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Regla no encontrada")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(rule, key, value)

    await db.flush()
    await db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPERVISOR])),
):
    result = await db.execute(select(DetectionRule).where(DetectionRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Regla no encontrada")
    rule.is_active = False
    await db.flush()


@router.get("/schedules", response_model=list[ScheduleResponse])
async def list_schedules(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Schedule).where(Schedule.is_active == True))
    return result.scalars().all()


@router.post("/schedules", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    data: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPERVISOR])),
):
    schedule = Schedule(**data.model_dump())
    db.add(schedule)
    await db.flush()
    await db.refresh(schedule)
    return schedule
