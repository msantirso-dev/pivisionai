"""Per-camera pipeline metrics (Redis-backed)."""

from __future__ import annotations

import logging
from typing import Any, Dict

import redis

from app.config import get_settings

logger = logging.getLogger(__name__)

METRIC_FIELDS = [
    "frames_received_total",
    "frames_discarded_no_motion_total",
    "frames_discarded_duplicate_total",
    "frames_discarded_sampler_total",
    "detector_calls_total",
    "llm_calls_sent_total",
    "llm_calls_avoided_total",
    "screenshots_saved_total",
    "screenshots_suppressed_total",
    "tokens_input_estimated",
    "tokens_output_estimated",
    "bandwidth_main_stream",
    "bandwidth_sub_stream",
]


class MetricsService:
    def __init__(self):
        self._redis = redis.from_url(get_settings().redis_url, decode_responses=True)

    def _key(self, camera_id: str) -> str:
        return f"pipeline:metrics:{camera_id}"

    def increment(self, camera_id: str, field: str, amount: int = 1) -> None:
        if field not in METRIC_FIELDS:
            return
        try:
            self._redis.hincrby(self._key(camera_id), field, amount)
        except Exception as exc:
            logger.debug("metrics increment failed: %s", exc)

    def record_latency(self, camera_id: str, field: str, ms: float) -> None:
        try:
            key = f"{self._key(camera_id)}:lat:{field}"
            self._redis.lpush(key, str(ms))
            self._redis.ltrim(key, 0, 99)
        except Exception as exc:
            logger.debug("metrics latency failed: %s", exc)

    def get_metrics(self, camera_id: str) -> Dict[str, Any]:
        try:
            data = self._redis.hgetall(self._key(camera_id)) or {}
            out = {f: int(data.get(f) or 0) for f in METRIC_FIELDS}
            for lat in ("decode", "prefilter", "detector", "llm", "total"):
                key = f"{self._key(camera_id)}:lat:{lat}_ms"
                samples = self._redis.lrange(key, 0, 19)
                if samples:
                    vals = [float(x) for x in samples]
                    out[f"latency_{lat}_ms"] = sum(vals) / len(vals)
                else:
                    out[f"latency_{lat}_ms"] = 0.0
            return out
        except Exception as exc:
            logger.warning("get_metrics failed: %s", exc)
            return {f: 0 for f in METRIC_FIELDS}


metrics_service = MetricsService()
