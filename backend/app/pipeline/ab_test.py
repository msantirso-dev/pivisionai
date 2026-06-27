"""A/B comparison main vs sub stream."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List

import redis

from app.config import get_settings
from app.pipeline.stream_selector import stream_selector


class ABTestService:
    def __init__(self):
        self._redis = redis.from_url(get_settings().redis_url, decode_responses=True)

    def _key(self, camera_id: str) -> str:
        return f"pipeline:ab:results:{camera_id}"

    def record_sample(
        self,
        camera_id: str,
        stream: str,
        metrics: Dict[str, Any],
    ) -> None:
        try:
            raw = self._redis.get(self._key(camera_id))
            data = json.loads(raw) if raw else {"main": [], "sub": []}
            bucket = "main" if stream == "main" else "sub"
            data.setdefault(bucket, []).append({**metrics, "ts": time.time()})
            data[bucket] = data[bucket][-50:]
            self._redis.setex(self._key(camera_id), 86400 * 14, json.dumps(data))
        except Exception:
            pass

    def compare(self, camera_id: str) -> Dict[str, Any]:
        try:
            raw = self._redis.get(self._key(camera_id))
            data = json.loads(raw) if raw else {"main": [], "sub": []}
        except Exception:
            data = {"main": [], "sub": []}

        def avg(samples: List[dict], field: str) -> float:
            vals = [s.get(field, 0) for s in samples if field in s]
            return sum(vals) / len(vals) if vals else 0.0

        main_s = data.get("main", [])
        sub_s = data.get("sub", [])
        comparison = {
            "main_samples": len(main_s),
            "sub_samples": len(sub_s),
            "main_detections_avg": avg(main_s, "detections"),
            "sub_detections_avg": avg(sub_s, "detections"),
            "main_latency_ms_avg": avg(main_s, "latency_ms"),
            "sub_latency_ms_avg": avg(sub_s, "latency_ms"),
            "main_bandwidth_avg": avg(main_s, "bytes"),
            "sub_bandwidth_avg": avg(sub_s, "bytes"),
            "main_false_positive_rate": avg(main_s, "false_positives"),
            "sub_false_positive_rate": avg(sub_s, "false_positives"),
        }

        recommendation = "hybrid"
        if comparison["sub_samples"] >= 3 and comparison["main_samples"] >= 3:
            if comparison["sub_detections_avg"] >= comparison["main_detections_avg"] * 0.9:
                if comparison["sub_bandwidth_avg"] < comparison["main_bandwidth_avg"] * 0.6:
                    recommendation = "sub"
            if comparison["main_detections_avg"] > comparison["sub_detections_avg"] * 1.2:
                recommendation = "main"
            else:
                recommendation = "hybrid"

        comparison["recommendation"] = recommendation
        savings_pct = 0.0
        if comparison["main_bandwidth_avg"] > 0:
            savings_pct = max(
                0.0,
                (1 - comparison["sub_bandwidth_avg"] / comparison["main_bandwidth_avg"]) * 100,
            )
        comparison["estimated_bandwidth_savings_pct"] = round(savings_pct, 1)
        stream_selector.set_recommendation(camera_id, recommendation if recommendation != "hybrid" else "sub")
        return comparison


ab_test_service = ABTestService()
