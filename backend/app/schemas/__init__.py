"""Pydantic schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models import EventSeverity, EventStatus, RuleType, UserRole


class DetectionRuleUpdate(BaseModel):
    name: Optional[str] = None
    severity: Optional[EventSeverity] = None
    geometry: Optional[Dict[str, Any]] = None
    object_classes: Optional[List[str]] = None
    min_confidence: Optional[float] = None
    actions: Optional[Dict[str, Any]] = None
    context_description: Optional[str] = None
    schedule_id: Optional[UUID] = None
    is_active: Optional[bool] = None


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    role: str
    exp: Optional[int] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None
    role: UserRole = UserRole.OPERATOR


class UserResponse(BaseModel):
    id: UUID
    email: str
    username: str
    full_name: Optional[str]
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CameraCreate(BaseModel):
    name: str
    location: Optional[str] = None
    ip_address: str
    port: int = 554
    username: str
    password: str
    brand: str = "dahua"
    model: Optional[str] = None
    rtsp_main: Optional[str] = None
    rtsp_sub: Optional[str] = None
    onvif_url: Optional[str] = None
    channel: int = 1
    site_id: Optional[UUID] = None
    group_id: Optional[UUID] = None
    zone: Optional[str] = None
    ai_enabled: bool = True
    ai_fps: int = 5
    ai_confidence: float = 0.45
    dahua_api_enabled: bool = True
    dahua_api_port: int = 80


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    ip_address: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    rtsp_main: Optional[str] = None
    rtsp_sub: Optional[str] = None
    zone: Optional[str] = None
    ai_enabled: Optional[bool] = None
    ai_fps: Optional[int] = None
    ai_confidence: Optional[float] = None
    is_active: Optional[bool] = None


class CameraResponse(BaseModel):
    id: UUID
    name: str
    location: Optional[str]
    ip_address: str
    port: int
    brand: str
    model: Optional[str]
    rtsp_main: str
    rtsp_sub: Optional[str]
    channel: int
    zone: Optional[str]
    status: str
    ai_enabled: bool
    ai_fps: int
    ai_confidence: float
    dahua_api_enabled: bool
    is_active: bool
    last_seen_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class CameraTestResult(BaseModel):
    success: bool
    message: str
    latency_ms: Optional[float] = None
    resolution: Optional[str] = None


class SnapshotResponse(BaseModel):
    camera_id: UUID
    file_path: str
    url: str
    width: int
    height: int
    captured_at: datetime


class DetectionRuleCreate(BaseModel):
    camera_id: UUID
    name: str
    rule_type: RuleType
    severity: EventSeverity = EventSeverity.MEDIUM
    geometry: Dict[str, Any] = Field(default_factory=dict)
    object_classes: List[str] = Field(default_factory=lambda: ["person", "car"])
    min_confidence: float = 0.45
    min_object_size: int = 20
    loitering_seconds: Optional[int] = None
    direction: Optional[str] = None
    actions: Dict[str, Any] = Field(default_factory=dict)
    context_description: Optional[str] = None
    schedule_id: Optional[UUID] = None


class DetectionRuleResponse(BaseModel):
    id: UUID
    camera_id: UUID
    name: str
    rule_type: RuleType
    severity: EventSeverity
    is_active: bool
    geometry: dict
    object_classes: list
    min_confidence: float
    actions: dict
    context_description: Optional[str] = None
    schedule_id: Optional[UUID]
    created_at: datetime

    model_config = {"from_attributes": True}


class ScheduleCreate(BaseModel):
    name: str
    timezone: str = "America/Argentina/Buenos_Aires"
    weekly: Dict[str, List[Dict[str, str]]] = Field(default_factory=dict)


class ScheduleResponse(BaseModel):
    id: UUID
    name: str
    timezone: str
    weekly: dict
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class EventResponse(BaseModel):
    id: UUID
    camera_id: UUID
    rule_id: Optional[UUID]
    event_type: str
    status: EventStatus
    severity: EventSeverity
    object_class: Optional[str]
    track_id: Optional[int]
    confidence: Optional[float]
    description: Optional[str]
    metadata: dict = Field(default_factory=dict, alias="metadata_")
    occurred_at: datetime
    created_at: datetime
    snapshot_url: Optional[str] = None

    model_config = {"from_attributes": True, "populate_by_name": True}


class EventUpdate(BaseModel):
    status: Optional[EventStatus] = None
    comment: Optional[str] = None
    assigned_to: Optional[UUID] = None


class EventBulkUpdate(BaseModel):
    event_ids: List[UUID]
    status: EventStatus
    comment: Optional[str] = None


class EventSearchParams(BaseModel):
    camera_id: Optional[UUID] = None
    object_class: Optional[str] = None
    severity: Optional[EventSeverity] = None
    status: Optional[EventStatus] = None
    rule_type: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = 50
    offset: int = 0


class OperatorActionCreate(BaseModel):
    action: str
    new_status: Optional[EventStatus] = None
    comment: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0-mvp"
    database: str
    redis: str
    timestamp: datetime


class SystemHealthResponse(BaseModel):
    cpu_percent: float
    ram_percent: float
    gpu_percent: Optional[float]
    vram_percent: Optional[float]
    disk_percent: float
    queue_size: int
    active_workers: int
    online_cameras: int
    offline_cameras: int
    error_cameras: int
    degraded_mode: bool
    cameras: List[Dict[str, Any]] = Field(default_factory=list)


class IntegrationCreate(BaseModel):
    name: str
    integration_type: str
    config: Dict[str, Any] = Field(default_factory=dict)


class IntegrationResponse(BaseModel):
    id: UUID
    name: str
    integration_type: str
    config: dict
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
