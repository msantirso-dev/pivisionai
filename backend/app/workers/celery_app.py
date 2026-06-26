"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "pivision",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_routes={
        "app.workers.tasks.analyze_camera_frame": {"queue": "ai"},
        "app.workers.tasks.start_camera_analysis": {"queue": "ai"},
        "app.workers.tasks.poll_all_cameras": {"queue": "ai"},
        "app.workers.tasks.poll_dahua_events": {"queue": "dahua"},
        "app.workers.tasks.process_ivs_event": {"queue": "dahua"},
        "app.workers.tasks.analyze_event_with_llm": {"queue": "ai"},
        "app.workers.tasks.send_event_notifications": {"queue": "notifications"},
        "app.workers.tasks.collect_system_health": {"queue": "default"},
    },
    beat_schedule={
        "poll-all-cameras": {
            "task": "app.workers.tasks.poll_all_cameras",
            "schedule": 10.0,
        },
        "poll-dahua-events": {
            "task": "app.workers.tasks.poll_dahua_events",
            "schedule": float(settings.dahua_poll_interval),
        },
        "collect-system-health": {
            "task": "app.workers.tasks.collect_system_health",
            "schedule": float(settings.health_check_interval),
        },
    },
)
