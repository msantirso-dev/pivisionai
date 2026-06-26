"""SQLAlchemy models for PI Vision AI."""

import enum
import uuid
from datetime import datetime, time
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    OPERATOR = "operator"
    READONLY = "readonly"


class EventStatus(str, enum.Enum):
    NEW = "new"
    SEEN = "seen"
    IN_PROGRESS = "in_progress"
    DISCARDED = "discarded"
    ESCALATED = "escalated"
    CLOSED = "closed"


class EventSeverity(str, enum.Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RuleType(str, enum.Enum):
    LINE_CROSSING = "line_crossing"
    ZONE_INTRUSION = "zone_intrusion"
    LOITERING = "loitering"
    ABANDONED_OBJECT = "abandoned_object"
    REMOVED_OBJECT = "removed_object"
    FORBIDDEN_PERSON = "forbidden_person"
    STOPPED_VEHICLE = "stopped_vehicle"
    WRONG_DIRECTION = "wrong_direction"
    PERSON_COUNT = "person_count"
    VEHICLE_COUNT = "vehicle_count"


class CameraStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    DEGRADED = "degraded"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.OPERATOR)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    operator_actions = relationship("OperatorAction", back_populates="operator")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    permissions: Mapped[dict] = mapped_column(JSONB, default=dict)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    address: Mapped[Optional[str]] = mapped_column(String(500))
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    camera_groups = relationship("CameraGroup", back_populates="site")
    cameras = relationship("Camera", back_populates="site")


class CameraGroup(Base):
    __tablename__ = "camera_groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    site = relationship("Site", back_populates="camera_groups")
    cameras = relationship("Camera", back_populates="group")


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id"))
    group_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("camera_groups.id"))
    name: Mapped[str] = mapped_column(String(255))
    location: Mapped[Optional[str]] = mapped_column(String(500))
    ip_address: Mapped[str] = mapped_column(String(45))
    port: Mapped[int] = mapped_column(Integer, default=554)
    username: Mapped[str] = mapped_column(String(100))
    password_encrypted: Mapped[str] = mapped_column(Text)
    brand: Mapped[str] = mapped_column(String(50), default="dahua")
    model: Mapped[Optional[str]] = mapped_column(String(100))
    rtsp_main: Mapped[str] = mapped_column(Text)
    rtsp_sub: Mapped[Optional[str]] = mapped_column(Text)
    onvif_url: Mapped[Optional[str]] = mapped_column(Text)
    channel: Mapped[int] = mapped_column(Integer, default=1)
    zone: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[CameraStatus] = mapped_column(Enum(CameraStatus), default=CameraStatus.OFFLINE)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_fps: Mapped[int] = mapped_column(Integer, default=5)
    ai_confidence: Mapped[float] = mapped_column(Float, default=0.45)
    ai_min_object_size: Mapped[int] = mapped_column(Integer, default=20)
    ai_analysis_width: Mapped[int] = mapped_column(Integer, default=640)
    ai_load_profile: Mapped[str] = mapped_column(String(20), default="medium")
    analysis_mode: Mapped[str] = mapped_column(String(30), default="continuous")
    dahua_api_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    dahua_api_port: Mapped[int] = mapped_column(Integer, default=80)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    site = relationship("Site", back_populates="cameras")
    group = relationship("CameraGroup", back_populates="cameras")
    streams = relationship("CameraStream", back_populates="camera")
    events = relationship("Event", back_populates="camera")
    detection_rules = relationship("DetectionRule", back_populates="camera")


class CameraStream(Base):
    __tablename__ = "camera_streams"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cameras.id"))
    stream_type: Mapped[str] = mapped_column(String(20))
    url: Mapped[str] = mapped_column(Text)
    resolution: Mapped[Optional[str]] = mapped_column(String(20))
    fps: Mapped[Optional[float]] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_frame_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    camera = relationship("Camera", back_populates="streams")


class AIModel(Base):
    __tablename__ = "ai_models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(50))
    model_path: Mapped[str] = mapped_column(Text)
    model_type: Mapped[str] = mapped_column(String(50), default="yolo")
    classes: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    device: Mapped[str] = mapped_column(String(20), default="cpu")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIWorker(Base):
    __tablename__ = "ai_workers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hostname: Mapped[str] = mapped_column(String(255))
    worker_id: Mapped[str] = mapped_column(String(255), unique=True)
    status: Mapped[str] = mapped_column(String(50), default="idle")
    assigned_cameras: Mapped[list] = mapped_column(JSONB, default=list)
    gpu_name: Mapped[Optional[str]] = mapped_column(String(255))
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DetectionRule(Base):
    __tablename__ = "detection_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cameras.id"))
    name: Mapped[str] = mapped_column(String(255))
    rule_type: Mapped[RuleType] = mapped_column(Enum(RuleType))
    severity: Mapped[EventSeverity] = mapped_column(Enum(EventSeverity), default=EventSeverity.MEDIUM)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    geometry: Mapped[dict] = mapped_column(JSONB, default=dict)
    object_classes: Mapped[list] = mapped_column(JSONB, default=list)
    min_confidence: Mapped[float] = mapped_column(Float, default=0.45)
    min_object_size: Mapped[int] = mapped_column(Integer, default=20)
    loitering_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    direction: Mapped[Optional[str]] = mapped_column(String(50))
    actions: Mapped[dict] = mapped_column(JSONB, default=dict)
    anti_fp_filters: Mapped[dict] = mapped_column(JSONB, default=dict)
    context_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    schedule_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("schedules.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    camera = relationship("Camera", back_populates="detection_rules")
    schedule = relationship("Schedule", back_populates="rules")


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(50), default="America/Argentina/Buenos_Aires")
    weekly: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    rules = relationship("DetectionRule", back_populates="schedule")


class Holiday(Base):
    __tablename__ = "holidays"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_exception: Mapped[bool] = mapped_column(Boolean, default=False)
    schedule_override: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cameras.id"))
    rule_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("detection_rules.id"))
    event_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[EventStatus] = mapped_column(Enum(EventStatus), default=EventStatus.NEW)
    severity: Mapped[EventSeverity] = mapped_column(Enum(EventSeverity), default=EventSeverity.MEDIUM)
    object_class: Mapped[Optional[str]] = mapped_column(String(50))
    track_id: Mapped[Optional[int]] = mapped_column(Integer)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    description: Mapped[Optional[str]] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    camera = relationship("Camera", back_populates="events")
    rule = relationship("DetectionRule")
    score = relationship("EventScore", back_populates="event", uselist=False)
    snapshots = relationship("EventSnapshot", back_populates="event")
    clips = relationship("EventClip", back_populates="event")
    operator_actions = relationship("OperatorAction", back_populates="event")


class EventScore(Base):
    __tablename__ = "event_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"), unique=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    classification: Mapped[str] = mapped_column(String(50), default="info")
    factors: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event = relationship("Event", back_populates="score")


class EventSnapshot(Base):
    __tablename__ = "event_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"))
    file_path: Mapped[str] = mapped_column(Text)
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    annotations: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event = relationship("Event", back_populates="snapshots")


class EventClip(Base):
    __tablename__ = "event_clips"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"))
    file_path: Mapped[str] = mapped_column(Text)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    pre_seconds: Mapped[int] = mapped_column(Integer, default=10)
    post_seconds: Mapped[int] = mapped_column(Integer, default=20)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event = relationship("Event", back_populates="clips")


class DahuaEvent(Base):
    __tablename__ = "dahua_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cameras.id"))
    event_type: Mapped[str] = mapped_column(String(100))
    raw_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    ivs_type: Mapped[Optional[str]] = mapped_column(String(100))
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_confirmed: Mapped[Optional[bool]] = mapped_column(Boolean)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CorrelatedEvent(Base):
    __tablename__ = "correlated_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dahua_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("dahua_events.id"))
    ai_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"))
    correlation_score: Mapped[float] = mapped_column(Float, default=0.0)
    ai_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    discarded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OperatorAction(Base):
    __tablename__ = "operator_actions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"))
    operator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100))
    previous_status: Mapped[Optional[str]] = mapped_column(String(50))
    new_status: Mapped[Optional[str]] = mapped_column(String(50))
    comment: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event = relationship("Event", back_populates="operator_actions")
    operator = relationship("User", back_populates="operator_actions")


class SystemHealthLog(Base):
    __tablename__ = "system_health_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cpu_percent: Mapped[float] = mapped_column(Float)
    ram_percent: Mapped[float] = mapped_column(Float)
    gpu_percent: Mapped[Optional[float]] = mapped_column(Float)
    vram_percent: Mapped[Optional[float]] = mapped_column(Float)
    disk_percent: Mapped[float] = mapped_column(Float)
    network_mbps: Mapped[Optional[float]] = mapped_column(Float)
    queue_size: Mapped[int] = mapped_column(Integer, default=0)
    active_workers: Mapped[int] = mapped_column(Integer, default=0)
    online_cameras: Mapped[int] = mapped_column(Integer, default=0)
    offline_cameras: Mapped[int] = mapped_column(Integer, default=0)
    error_cameras: Mapped[int] = mapped_column(Integer, default=0)
    degraded_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    channel_type: Mapped[str] = mapped_column(String(50))
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"))
    channel_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("notification_channels.id"))
    channel_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    response: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Integration(Base):
    __tablename__ = "integrations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    integration_type: Mapped[str] = mapped_column(String(50))
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[Optional[str]] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
