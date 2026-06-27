"""Intelligent main/sub stream selection."""

from __future__ import annotations

from typing import Literal, Optional

import redis

from app.config import get_settings
from app.pipeline.camera_config import CameraPipelineConfig
from app.pipeline.metrics import metrics_service

StreamChoice = Literal["main", "sub", "http"]


class StreamSelector:
    def __init__(self):
        self._redis = redis.from_url(get_settings().redis_url, decode_responses=True)

    def _ab_key(self, camera_id: str) -> str:
        return f"pipeline:ab:mode:{camera_id}"

    def select(
        self,
        camera_id: str,
        config: CameraPipelineConfig,
        important_event: bool = False,
        is_cloud: bool = False,
    ) -> StreamChoice:
        if is_cloud:
            return "http"

        mode = config.stream_mode
        if important_event and mode in ("hybrid", "auto", "main"):
            metrics_service.increment(camera_id, "bandwidth_main_stream", 1)
            return "main"

        if mode == "main":
            metrics_service.increment(camera_id, "bandwidth_main_stream", 1)
            return "main"

        if mode == "sub":
            metrics_service.increment(camera_id, "bandwidth_sub_stream", 1)
            return "sub"

        if mode == "hybrid":
            metrics_service.increment(camera_id, "bandwidth_sub_stream", 1)
            return "sub"

        # auto: read recommendation from A/B or default sub
        rec = self.get_recommendation(camera_id)
        if rec == "main":
            metrics_service.increment(camera_id, "bandwidth_main_stream", 1)
            return "main"
        metrics_service.increment(camera_id, "bandwidth_sub_stream", 1)
        return "sub"

    def get_recommendation(self, camera_id: str) -> str:
        try:
            return self._redis.get(self._ab_key(camera_id)) or "sub"
        except Exception:
            return "sub"

    def set_recommendation(self, camera_id: str, mode: str) -> None:
        try:
            self._redis.setex(self._ab_key(camera_id), 86400 * 7, mode)
        except Exception:
            pass


stream_selector = StreamSelector()
