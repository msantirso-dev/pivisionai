"""Frame rate limiting per camera."""

from __future__ import annotations

import time

import redis

from app.config import get_settings
from app.pipeline.camera_config import CameraPipelineConfig


class FrameSampler:
    def __init__(self):
        self._redis = redis.from_url(get_settings().redis_url, decode_responses=True)

    def _key(self, camera_id: str, kind: str) -> str:
        return f"pipeline:sampler:{camera_id}:{kind}"

    def should_sample(self, camera_id: str, config: CameraPipelineConfig, kind: str = "analysis") -> bool:
        fps = config.detector_fps if kind == "detector" else config.analysis_fps
        if fps <= 0:
            return True
        interval = 1.0 / fps
        key = self._key(camera_id, kind)
        now = time.time()
        try:
            last = self._redis.get(key)
            if last and (now - float(last)) < interval:
                return False
            self._redis.setex(key, max(60, int(interval * 10)), str(now))
            return True
        except Exception:
            return True


frame_sampler = FrameSampler()
