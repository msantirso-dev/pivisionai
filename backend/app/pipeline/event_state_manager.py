"""Track-aware event deduplication and cooldown."""

from __future__ import annotations

import time
from typing import Dict, Optional, Tuple

import redis

from app.config import get_settings


class EventStateManager:
    def __init__(self):
        self._redis = redis.from_url(get_settings().redis_url, decode_responses=True)

    def _key(self, camera_id: str, rule_id: str, track_id: Optional[int]) -> str:
        tid = track_id if track_id is not None else "none"
        return f"pipeline:eventstate:{camera_id}:{rule_id}:{tid}"

    def should_emit(
        self,
        camera_id: str,
        rule_id: str,
        track_id: Optional[int],
        event_type: str,
        cooldown_seconds: int,
    ) -> Tuple[bool, str]:
        key = self._key(camera_id, rule_id, track_id)
        now = time.time()
        try:
            raw = self._redis.get(key)
            if raw:
                parts = raw.split("|", 2)
                prev_type = parts[0] if parts else ""
                prev_ts = float(parts[1]) if len(parts) > 1 else 0
                if prev_type == event_type and (now - prev_ts) < cooldown_seconds:
                    return False, "cooldown"
            self._redis.setex(key, max(cooldown_seconds * 2, 120), f"{event_type}|{now}|1")
            return True, "new"
        except Exception:
            return True, "redis_unavailable"


event_state_manager = EventStateManager()
