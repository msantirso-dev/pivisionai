"""Celery worker tasks for AI analysis, Dahua polling, and notifications."""

import asyncio
import logging
import os
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import (
    Camera,
    CameraStatus,
    CorrelatedEvent,
    DahuaEvent,
    DetectionRule,
    Event,
    EventScore,
    EventSeverity,
    EventSnapshot,
    Schedule,
    SystemHealthLog,
)
from app.services.ai_service import ai_service
from app.services.correlation_service import correlate_ivs_with_ai, should_discard_ivs
from app.services.dahua_service import dahua_api_service
from app.services.event_scorer import calculate_event_score
from app.pipeline.semantic_cache import semantic_cache
from app.services.event_review import build_review_description
from app.services.health_service import health_service
from app.services.notification_service import notification_service
from app.pipeline.geometry import scale_geometry
from app.pipeline.orchestrator import analysis_orchestrator
from app.pipeline.camera_config import CameraPipelineConfig
from app.services.camera_capture import capture_frame_np, capture_live_frame
from app.services.rtsp_service import resolve_camera_rtsp_urls, rtsp_service
from app.services.websocket_manager import ws_manager
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)
settings = get_settings()

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
WorkerSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.run_until_complete(engine.dispose())
        loop.close()


def _should_send_external_notifications(actions: dict) -> bool:
    if not actions:
        return False
    return bool(actions.get("telegram") or actions.get("webhook") or actions.get("mqtt"))


def _llm_state_signature(camera: Camera, triggered: dict) -> str:
    return semantic_cache.build_signature(
        triggered.get("track_id"),
        triggered.get("object_class") or "",
        str(triggered.get("rule_id") or "none"),
        triggered.get("event_type", ""),
        1,
    )


async def _resolve_llm_for_event(
    session: AsyncSession, camera: Camera, triggered: dict, has_snapshot: bool = True
) -> tuple[bool, dict | None]:
    """Return (call_llm, cached_analysis). UI observations always attempt cache reuse."""
    if not has_snapshot:
        return False, None

    actions = triggered.get("actions") or {}
    if actions.get("llm_describe") is False:
        return False, None

    pipeline_cfg = CameraPipelineConfig.from_camera(camera)
    if not pipeline_cfg.llm_enabled:
        return False, None

    from app.services.llm_config import load_llm_config
    from app.pipeline.metrics import metrics_service

    cfg = await load_llm_config(session)
    if not (cfg.get("enabled") and cfg.get("analyze_on_event")):
        return False, None

    sig = _llm_state_signature(camera, triggered)
    track_id = triggered.get("track_id")
    call, cached = semantic_cache.should_call_llm(
        str(camera.id), track_id, sig, pipeline_cfg.cooldown_seconds
    )
    if not call and cached:
        analysis = cached.get("analysis") or {}
        parsed = (analysis.get("parsed") or {}) if isinstance(analysis, dict) else {}
        if parsed.get("summary") or analysis.get("text"):
            metrics_service.increment(str(camera.id), "llm_calls_avoided_total")
            return False, analysis

    return True, None


async def _should_analyze_event_with_llm(
    session: AsyncSession, camera: Camera, triggered: dict
) -> bool:
    call, _ = await _resolve_llm_for_event(session, camera, triggered)
    return call


async def _get_camera_rules(session: AsyncSession, camera_id: UUID):
    rules_result = await session.execute(
        select(DetectionRule).where(
            DetectionRule.camera_id == camera_id,
            DetectionRule.is_active == True,
        )
    )
    rules = rules_result.scalars().all()

    schedule_ids = [r.schedule_id for r in rules if r.schedule_id]
    schedule_map = {}
    if schedule_ids:
        sched_result = await session.execute(select(Schedule).where(Schedule.id.in_(schedule_ids)))
        for s in sched_result.scalars().all():
            schedule_map[str(s.id)] = {
                "timezone": s.timezone,
                "weekly": s.weekly,
            }

    rules_data = [
        {
            "id": str(r.id),
            "name": r.name,
            "rule_type": r.rule_type.value if hasattr(r.rule_type, "value") else r.rule_type,
            "severity": r.severity.value if hasattr(r.severity, "value") else r.severity,
            "geometry": r.geometry,
            "object_classes": r.object_classes,
            "min_confidence": r.min_confidence,
            "actions": r.actions,
            "context_description": r.context_description or "",
            "schedule_id": str(r.schedule_id) if r.schedule_id else None,
            "is_active": r.is_active,
        }
        for r in rules
    ]
    return rules_data, schedule_map


async def _create_event(session: AsyncSession, camera: Camera, triggered: dict):
    severity = triggered.get("severity", "medium")
    if isinstance(severity, str):
        try:
            severity = EventSeverity(severity)
        except ValueError:
            severity = EventSeverity.MEDIUM

    event = Event(
        camera_id=camera.id,
        rule_id=UUID(triggered["rule_id"]) if triggered.get("rule_id") else None,
        event_type=triggered["event_type"],
        severity=severity,
        object_class=triggered.get("object_class"),
        track_id=triggered.get("track_id"),
        confidence=triggered.get("confidence"),
        description=triggered.get("description"),
        metadata_={
            **triggered.get("metadata", {}),
            "rule_name": triggered.get("rule_name"),
            "context_description": triggered.get("context_description") or "",
        },
    )
    session.add(event)
    await session.flush()

    score_data = calculate_event_score(
        {
            "severity": severity.value if hasattr(severity, "value") else severity,
            "object_class": triggered.get("object_class"),
            "confidence": triggered.get("confidence"),
        },
        rule=triggered,
        camera={"zone": camera.zone},
    )
    session.add(
        EventScore(
            event_id=event.id,
            score=score_data["score"],
            classification=score_data["classification"],
            factors=score_data["factors"],
        )
    )

    import os
    from datetime import datetime, timezone

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    pipeline_cfg = CameraPipelineConfig.from_camera(camera)
    zone_key = str(triggered.get("rule_id") or "global")

    jpeg_bytes = triggered.get("_pipeline_jpeg")
    width = triggered.get("_pipeline_fw")
    height = triggered.get("_pipeline_fh")
    if not jpeg_bytes:
        jpeg_bytes, width, height, _source = capture_live_frame(camera)

    snapshot_url = None
    filepath = None
    if jpeg_bytes:
        filepath, snapshot_url = analysis_orchestrator.attach_event_snapshot(
            str(camera.id),
            jpeg_bytes,
            pipeline_cfg,
            zone_key,
            str(event.id),
            timestamp,
            triggered.get("metadata", {}),
        )

    if filepath:
        session.add(
            EventSnapshot(
                event_id=event.id,
                file_path=filepath,
                width=width or 0,
                height=height or 0,
                annotations=triggered.get("metadata", {}),
            )
        )

    await session.commit()
    await session.refresh(event)

    actions = triggered.get("actions", {})
    run_llm_describe, cached_analysis = await _resolve_llm_for_event(
        session, camera, triggered, has_snapshot=bool(filepath)
    )
    if cached_analysis:
        meta = dict(event.metadata_ or {})
        meta["llm_analysis"] = cached_analysis
        meta["llm_reused"] = True
        event.metadata_ = meta
        parsed = cached_analysis.get("parsed") or {}
        review_text = build_review_description(parsed, event.description or "")
        if review_text:
            event.description = review_text
        await session.commit()
        await session.refresh(event)

    defer_notifications = run_llm_describe and _should_send_external_notifications(actions)

    event_dict = {
        "id": str(event.id),
        "camera_id": str(event.camera_id),
        "event_type": event.event_type,
        "severity": event.severity.value if hasattr(event.severity, "value") else event.severity,
        "object_class": event.object_class,
        "description": event.description,
        "confidence": event.confidence,
        "occurred_at": event.occurred_at.isoformat(),
        "metadata": event.metadata_,
        "score": score_data,
        "snapshot_url": snapshot_url,
        "status": event.status.value if hasattr(event.status, "value") else event.status,
        "actions": actions,
        "llm_pending": run_llm_describe,
        "llm_updated": bool(cached_analysis),
    }

    await ws_manager.send_event(event_dict)

    if defer_notifications:
        analyze_event_with_llm.delay(str(event.id), actions, notify_after=True)
    else:
        if _should_send_external_notifications(actions):
            send_event_notifications.delay(str(event.id), actions)
        if run_llm_describe:
            analyze_event_with_llm.delay(str(event.id))

    return event


@celery_app.task(name="app.workers.tasks.analyze_camera_frame", bind=True, max_retries=3)
def analyze_camera_frame(self, camera_id: str):
    async def _analyze():
        async with WorkerSession() as session:
            result = await session.execute(select(Camera).where(Camera.id == UUID(camera_id)))
            camera = result.scalar_one_or_none()
            if not camera or not camera.is_active or not camera.ai_enabled:
                return

            rules_data, schedule_map = await _get_camera_rules(session, camera.id)
            pipeline_result = analysis_orchestrator.process_frame(
                camera, camera_id, rules_data, schedule_map
            )

            if pipeline_result.skipped:
                if pipeline_result.skip_reason == "no_frame":
                    camera.status = CameraStatus.OFFLINE
                    await session.commit()
                    logger.debug("Camera %s skipped: %s", camera_id, pipeline_result.skip_reason)
                return

            camera.status = CameraStatus.ONLINE
            camera.last_seen_at = datetime.now(timezone.utc)

            if pipeline_result.detections:
                logger.info(
                    "Camera %s: %d detections via %s, %d rules triggered (pipeline)",
                    camera_id,
                    len(pipeline_result.detections),
                    pipeline_result.frame_source,
                    len(pipeline_result.triggered_events),
                )

            for triggered in pipeline_result.triggered_events:
                await _create_event(session, camera, triggered)

            await session.commit()

    try:
        run_async(_analyze())
    except Exception as exc:
        logger.error("Analysis failed for camera %s: %s", camera_id, exc)
        raise self.retry(exc=exc, countdown=settings.rtsp_reconnect_delay)


@celery_app.task(name="app.workers.tasks.start_camera_analysis")
def start_camera_analysis(camera_id: str):
    """Schedule periodic analysis for a camera."""
    camera = camera_id
    analyze_camera_frame.apply_async(args=[camera], queue="ai")
    logger.info("Started analysis for camera %s", camera_id)


@celery_app.task(name="app.workers.tasks.poll_all_cameras")
def poll_all_cameras():
    async def _poll():
        async with WorkerSession() as session:
            result = await session.execute(
                select(Camera).where(Camera.is_active == True, Camera.ai_enabled == True)
            )
            cameras = result.scalars().all()
            for camera in cameras:
                analyze_camera_frame.apply_async(args=[str(camera.id)], queue="ai")

    run_async(_poll())


@celery_app.task(name="app.workers.tasks.process_ivs_event")
def process_ivs_event(dahua_event_id: str, camera_id: str):
    """Validate Dahua IVS event with AI and create correlation."""

    async def _process():
        async with WorkerSession() as session:
            dahua = await session.get(DahuaEvent, UUID(dahua_event_id))
            result = await session.execute(select(Camera).where(Camera.id == UUID(camera_id)))
            camera = result.scalar_one_or_none()
            if not dahua or not camera:
                return

            rtsp_main, rtsp_sub = resolve_camera_rtsp_urls(camera)
            rtsp_url = rtsp_sub if settings.use_substream_for_ai and rtsp_sub else rtsp_main
            frame = rtsp_service.read_frame(rtsp_url)
            if frame is None:
                dahua.processed = True
                dahua.ai_confirmed = False
                await session.commit()
                return

            detections = ai_service.detect(frame, confidence=camera.ai_confidence)
            correlation = correlate_ivs_with_ai(dahua.event_type, detections, camera.ai_confidence)

            dahua.processed = True
            dahua.ai_confirmed = correlation["ai_confirmed"]

            discard = should_discard_ivs(correlation, discard_unconfirmed=True)
            ai_event = None

            if correlation["ai_confirmed"]:
                severity = EventSeverity.MEDIUM
                if dahua.event_type in ("intrusion", "tripwire"):
                    severity = EventSeverity.HIGH

                ai_event = Event(
                    camera_id=camera.id,
                    event_type=f"ivs_{dahua.event_type}",
                    severity=severity,
                    object_class=correlation.get("matched_class"),
                    confidence=correlation.get("matched_confidence"),
                    description=f"IVS {dahua.event_type} confirmado por IA ({correlation.get('matched_class')})",
                    metadata_={
                        "ivs_type": dahua.ivs_type,
                        "dahua_event_id": str(dahua.id),
                        "correlation": correlation,
                    },
                )
                session.add(ai_event)
                await session.flush()

                session.add(
                    CorrelatedEvent(
                        dahua_event_id=dahua.id,
                        ai_event_id=ai_event.id,
                        correlation_score=correlation["correlation_score"],
                        ai_confirmed=True,
                        discarded=False,
                    )
                )

                snapshot = rtsp_service.capture_snapshot(rtsp_url, camera.id)
                if snapshot:
                    filepath, width, height = snapshot
                    session.add(
                        EventSnapshot(
                            event_id=ai_event.id,
                            file_path=filepath,
                            width=width,
                            height=height,
                        )
                    )

                await ws_manager.send_event(
                    {
                        "id": str(ai_event.id),
                        "camera_id": str(camera.id),
                        "event_type": ai_event.event_type,
                        "severity": severity.value,
                        "object_class": ai_event.object_class,
                        "description": ai_event.description,
                        "occurred_at": ai_event.occurred_at.isoformat(),
                        "metadata": ai_event.metadata_,
                        "source": "ivs_ai_correlation",
                    }
                )
                analyze_event_with_llm.delay(str(ai_event.id))
            else:
                dahua.ai_confirmed = False

            await session.commit()

    run_async(_process())


@celery_app.task(name="app.workers.tasks.poll_dahua_events")
def poll_dahua_events():
    async def _poll():
        async with WorkerSession() as session:
            result = await session.execute(
                select(Camera).where(
                    Camera.is_active == True,
                    Camera.dahua_api_enabled == True,
                    Camera.brand == "dahua",
                )
            )
            cameras = result.scalars().all()

            for camera in cameras:
                if getattr(camera, "connection_mode", "local") == "cloud" or not camera.ip_address:
                    continue
                events = await dahua_api_service.poll_events(
                    camera.ip_address,
                    camera.dahua_api_port,
                    camera.username,
                    camera.password_encrypted,
                )
                for evt in events:
                    dahua_event = DahuaEvent(
                        camera_id=camera.id,
                        event_type=evt["event_type"],
                        ivs_type=evt.get("ivs_type"),
                        raw_payload=evt.get("raw_payload", {}),
                    )
                    session.add(dahua_event)
                    await session.flush()

                    if camera.ai_enabled:
                        process_ivs_event.delay(str(dahua_event.id), str(camera.id))

            await session.commit()

    run_async(_poll())


@celery_app.task(name="app.workers.tasks.send_event_notifications")
def send_event_notifications(event_id: str, actions: dict):
    async def _notify():
        async with WorkerSession() as session:
            result = await session.execute(
                select(Event)
                .options(selectinload(Event.snapshots))
                .where(Event.id == UUID(event_id))
            )
            event = result.scalar_one_or_none()
            if not event:
                return

            cam_result = await session.execute(select(Camera).where(Camera.id == event.camera_id))
            camera = cam_result.scalar_one_or_none()

            snapshot_path = None
            snapshot_url = None
            if event.snapshots:
                import os

                snapshot_path = event.snapshots[0].file_path
                snapshot_url = f"/api/v1/evidence/snapshots/{os.path.basename(snapshot_path)}"

            event_dict = {
                "id": str(event.id),
                "camera_id": str(event.camera_id),
                "camera_name": camera.name if camera else "",
                "event_type": event.event_type,
                "severity": event.severity.value if hasattr(event.severity, "value") else event.severity,
                "object_class": event.object_class,
                "description": event.description,
                "confidence": event.confidence,
                "occurred_at": event.occurred_at.isoformat(),
                "metadata": event.metadata_,
                "snapshot_path": snapshot_path,
                "snapshot_url": snapshot_url,
            }
            results = await notification_service.notify_event(event_dict, actions or {})
            logger.info("Notifications for event %s: %s", event_id, results)

    run_async(_notify())


@celery_app.task(name="app.workers.tasks.analyze_event_with_llm")
def analyze_event_with_llm(event_id: str, actions: dict | None = None, notify_after: bool = False):
    """Analyze event snapshot with Ollama or OpenAI vision."""

    async def _analyze():
        from app.services.llm_config import load_llm_config
        from app.services.llm_cooldown import release_describe_slot
        from app.services.llm_service import llm_vision_service

        async with WorkerSession() as session:
            cfg = await load_llm_config(session)

            result = await session.execute(select(Event).where(Event.id == UUID(event_id)))
            event = result.scalar_one_or_none()
            if not event:
                return

            if not cfg.get("enabled") or not cfg.get("analyze_on_event"):
                if event.rule_id:
                    release_describe_slot(str(event.rule_id))
                return

            cam_result = await session.execute(select(Camera).where(Camera.id == event.camera_id))
            camera = cam_result.scalar_one_or_none()

            pipeline_cfg = CameraPipelineConfig.from_camera(camera) if camera else CameraPipelineConfig()
            if not pipeline_cfg.llm_enabled:
                if event.rule_id:
                    release_describe_slot(str(event.rule_id))
                return

            snap_result = await session.execute(
                select(EventSnapshot)
                .where(EventSnapshot.event_id == event.id)
                .order_by(EventSnapshot.created_at.desc())
            )
            snapshot = snap_result.scalars().first()
            snapshot_url = (
                f"/api/v1/evidence/snapshots/{os.path.basename(snapshot.file_path)}"
                if snapshot
                else None
            )

            if event.track_id is not None and camera:
                sig = _llm_state_signature(camera, {
                    "track_id": event.track_id,
                    "object_class": event.object_class,
                    "rule_id": str(event.rule_id) if event.rule_id else None,
                    "event_type": event.event_type,
                })
                call, cached = semantic_cache.should_call_llm(
                    str(event.camera_id), event.track_id, sig, pipeline_cfg.cooldown_seconds
                )
                analysis = (cached or {}).get("analysis") or {}
                parsed = analysis.get("parsed") or {}
                if not call and cached and (parsed.get("summary") or analysis.get("text")):
                    from app.pipeline.metrics import metrics_service

                    metrics_service.increment(str(event.camera_id), "llm_calls_avoided_total")
                    meta = dict(event.metadata_ or {})
                    meta["llm_analysis"] = cached.get("analysis", {})
                    meta["llm_reused"] = True
                    event.metadata_ = meta
                    parsed = (cached.get("analysis") or {}).get("parsed") or {}
                    review_text = build_review_description(parsed, event.description or "")
                    if review_text:
                        event.description = review_text
                    await session.commit()
                    if event.rule_id:
                        release_describe_slot(str(event.rule_id))
                    if notify_after and actions and _should_send_external_notifications(actions):
                        send_event_notifications.delay(event_id, actions)
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
                    return

            if not snapshot:
                if event.rule_id:
                    release_describe_slot(str(event.rule_id))
                if notify_after and actions and _should_send_external_notifications(actions):
                    send_event_notifications.delay(event_id, actions)
                return

            meta = event.metadata_ or {}
            rule_name = meta.get("rule_name")
            context_description = meta.get("context_description") or ""

            if event.rule_id and not context_description:
                rule_result = await session.execute(
                    select(DetectionRule).where(DetectionRule.id == event.rule_id)
                )
                rule = rule_result.scalar_one_or_none()
                if rule:
                    rule_name = rule_name or rule.name
                    context_description = rule.context_description or ""

            context = {
                "camera_name": camera.name if camera else "",
                "location": camera.location if camera else "",
                "event_type": event.event_type,
                "object_class": event.object_class,
                "description": event.description,
                "rule_name": rule_name,
                "context_description": context_description,
                "source": "event_auto",
            }

            from app.pipeline.metrics import metrics_service

            metrics_service.increment(str(event.camera_id), "llm_calls_sent_total")
            analysis = await llm_vision_service.analyze_image_file(
                snapshot.file_path, context, cfg
            )
            if not analysis.get("success"):
                logger.warning("LLM analysis failed for event %s: %s", event_id, analysis.get("error"))
                if event.rule_id:
                    release_describe_slot(str(event.rule_id))
                if notify_after and actions and _should_send_external_notifications(actions):
                    send_event_notifications.delay(event_id, actions)
                return

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
            if parsed.get("threat_level") == "critical":
                event.severity = EventSeverity.CRITICAL
            elif parsed.get("threat_level") == "high":
                event.severity = EventSeverity.HIGH

            if event.track_id is not None:
                sig = semantic_cache.build_signature(
                    event.track_id,
                    event.object_class or "",
                    str(event.rule_id or "none"),
                    event.event_type,
                    1,
                )
                semantic_cache.store(
                    str(event.camera_id),
                    event.track_id,
                    sig,
                    meta.get("llm_analysis", {}),
                )

            await session.commit()

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

            if notify_after and actions and _should_send_external_notifications(actions):
                send_event_notifications.delay(event_id, actions)

    run_async(_analyze())


@celery_app.task(name="app.workers.tasks.collect_system_health")
def collect_system_health():
    async def _collect():
        metrics = health_service.get_system_metrics()
        async with WorkerSession() as session:
            cameras = await health_service.get_camera_health(session)
            online = sum(1 for c in cameras if c["status"] == "online")
            offline = sum(1 for c in cameras if c["status"] == "offline")
            errors = sum(1 for c in cameras if c["status"] == "error")

            log = SystemHealthLog(
                cpu_percent=metrics["cpu_percent"],
                ram_percent=metrics["ram_percent"],
                gpu_percent=metrics.get("gpu_percent"),
                vram_percent=metrics.get("vram_percent"),
                disk_percent=metrics["disk_percent"],
                queue_size=0,
                active_workers=0,
                online_cameras=online,
                offline_cameras=offline,
                error_cameras=errors,
                degraded_mode=metrics["degraded_mode"],
            )
            session.add(log)
            await session.commit()

            await ws_manager.send_health(
                {
                    **metrics,
                    "online_cameras": online,
                    "offline_cameras": offline,
                    "error_cameras": errors,
                    "cameras": cameras,
                }
            )

    run_async(_collect())
