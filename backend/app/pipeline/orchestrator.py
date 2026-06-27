"""Event-driven analysis orchestrator."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.pipeline.ab_test import ab_test_service
from app.pipeline.camera_config import CameraPipelineConfig
from app.pipeline.event_state_manager import event_state_manager
from app.pipeline.evidence_deduplicator import evidence_deduplicator
from app.pipeline.frame_sampler import frame_sampler
from app.pipeline.llm_analyzer import apply_llm_gate_to_actions, should_invoke_llm
from app.pipeline.metrics import metrics_service
from app.pipeline.preprocessor import opencv_preprocessor
from app.pipeline.roi_filter import roi_filter
from app.pipeline.stream_manager import stream_manager
from app.pipeline.stream_selector import stream_selector
from app.pipeline.tracker_service import tracker_service
from app.services.ai_service import Detection
from app.pipeline.geometry import scale_geometry
from app.services.rule_engine import rule_engine

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    skipped: bool = False
    skip_reason: str = ""
    frame_source: str = ""
    detections: List[Detection] = field(default_factory=list)
    triggered_events: List[dict] = field(default_factory=list)
    frame_w: int = 0
    frame_h: int = 0
    metrics: Dict[str, Any] = field(default_factory=dict)


class AnalysisOrchestrator:
    def process_frame(
        self,
        camera,
        camera_id: str,
        rules_data: List[dict],
        schedule_map: dict,
        important_event: bool = False,
    ) -> PipelineResult:
        t0 = time.perf_counter()
        config = CameraPipelineConfig.from_camera(camera)
        result = PipelineResult()

        if not config.pipeline_enabled:
            return self._legacy_path(camera, camera_id, rules_data, schedule_map, result)

        if not frame_sampler.should_sample(camera_id, config, "analysis"):
            metrics_service.increment(camera_id, "frames_discarded_sampler_total")
            result.skipped = True
            result.skip_reason = "sampler"
            return result

        is_cloud = getattr(camera, "connection_mode", "local") == "cloud"
        stream = stream_selector.select(camera_id, config, important_event, is_cloud)
        t_decode = time.perf_counter()
        frame, fw, fh, source, nbytes = stream_manager.capture(camera, config, stream, important_event)
        decode_ms = (time.perf_counter() - t_decode) * 1000
        metrics_service.record_latency(camera_id, "decode_ms", decode_ms)

        if frame is None:
            result.skipped = True
            result.skip_reason = "no_frame"
            return result

        metrics_service.increment(camera_id, "frames_received_total")
        result.frame_source = source

        t_pre = time.perf_counter()
        frame = opencv_preprocessor.resize_for_analysis(frame, config.analysis_resolution)
        fw, fh = frame.shape[1], frame.shape[0]

        motion_area = opencv_preprocessor.motion_area(camera_id, frame, config)
        if motion_area < config.min_motion_area:
            metrics_service.increment(camera_id, "frames_discarded_no_motion_total")
            result.skipped = True
            result.skip_reason = "no_motion"
            metrics_service.record_latency(camera_id, "prefilter_ms", (time.perf_counter() - t_pre) * 1000)
            return result

        if not roi_filter.motion_in_roi(frame, motion_area, config):
            metrics_service.increment(camera_id, "frames_discarded_no_motion_total")
            result.skipped = True
            result.skip_reason = "motion_outside_roi"
            return result

        dup, dup_reason = opencv_preprocessor.is_duplicate(camera_id, frame, config)
        if dup:
            metrics_service.increment(camera_id, "frames_discarded_duplicate_total")
            result.skipped = True
            result.skip_reason = f"duplicate_{dup_reason}"
            metrics_service.record_latency(camera_id, "prefilter_ms", (time.perf_counter() - t_pre) * 1000)
            return result

        metrics_service.record_latency(camera_id, "prefilter_ms", (time.perf_counter() - t_pre) * 1000)

        if not frame_sampler.should_sample(camera_id, config, "detector"):
            result.skipped = True
            result.skip_reason = "detector_sampler"
            return result

        t_det = time.perf_counter()
        detections = tracker_service.detect_and_track(
            camera_id,
            frame,
            config,
            camera.ai_confidence,
            camera.ai_min_object_size,
        )
        detections = [d for d in detections if roi_filter.center_in_roi(d.center, config)]
        metrics_service.increment(camera_id, "detector_calls_total")
        metrics_service.record_latency(camera_id, "detector_ms", (time.perf_counter() - t_det) * 1000)

        scaled_rules = []
        for rule in rules_data:
            scaled = dict(rule)
            scaled["geometry"] = scale_geometry(rule.get("geometry", {}), fw, fh)
            scaled_rules.append(scaled)

        triggered = rule_engine.evaluate_rules(camera_id, detections, scaled_rules, schedule_map)

        filtered: List[dict] = []
        for trig in triggered:
            emit, _ = event_state_manager.should_emit(
                camera_id,
                str(trig.get("rule_id") or "none"),
                trig.get("track_id"),
                trig.get("event_type", ""),
                config.cooldown_seconds,
            )
            if not emit:
                continue
            allow_llm, _ = should_invoke_llm(
                camera_id, config, trig, len(detections)
            )
            trig = dict(trig)
            trig["actions"] = apply_llm_gate_to_actions(trig, allow_llm)
            if not allow_llm:
                trig.setdefault("metadata", {})["llm_reused"] = True
            filtered.append(trig)

        if config.enable_ab_test:
            ab_test_service.record_sample(
                camera_id,
                stream,
                {
                    "detections": len(detections),
                    "latency_ms": (time.perf_counter() - t0) * 1000,
                    "bytes": nbytes,
                    "false_positives": 0,
                },
            )

        result.detections = detections
        result.triggered_events = filtered
        result.frame_w = fw
        result.frame_h = fh
        metrics_service.record_latency(camera_id, "total_ms", (time.perf_counter() - t0) * 1000)
        return result

    def _legacy_path(
        self,
        camera,
        camera_id: str,
        rules_data: List[dict],
        schedule_map: dict,
        result: PipelineResult,
    ) -> PipelineResult:
        from app.services.camera_capture import capture_frame_np
        from app.services.ai_service import ai_service

        frame, fw, fh, source = capture_frame_np(camera)
        if frame is None:
            result.skipped = True
            result.skip_reason = "no_frame"
            return result
        detections = ai_service.detect(frame, confidence=camera.ai_confidence, min_object_size=camera.ai_min_object_size)
        detections = ai_service.assign_track_ids(camera_id, detections, frame_width=fw)
        scaled_rules = []
        for rule in rules_data:
            scaled = dict(rule)
            scaled["geometry"] = scale_geometry(rule.get("geometry", {}), fw, fh)
            scaled_rules.append(scaled)
        result.frame_source = source
        result.detections = detections
        result.triggered_events = rule_engine.evaluate_rules(camera_id, detections, scaled_rules, schedule_map)
        result.frame_w = fw
        result.frame_h = fh
        return result

    def should_save_snapshot(self, camera_id: str, jpeg_bytes: bytes, config: CameraPipelineConfig, zone: str = "global") -> bool:
        ok, reason = evidence_deduplicator.should_save(
            camera_id, jpeg_bytes, config.phash_threshold, zone
        )
        if ok:
            metrics_service.increment(camera_id, "screenshots_saved_total")
        else:
            metrics_service.increment(camera_id, "screenshots_suppressed_total")
        return ok


analysis_orchestrator = AnalysisOrchestrator()
