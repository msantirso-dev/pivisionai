"""Reuse LLM analysis when track state unchanged."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional, Tuple

import redis

from app.config import get_settings


class SemanticCache:
    def __init__(self):
        self._redis = redis.from_url(get_settings().redis_url, decode_responses=True)

    def _track_key(self, camera_id: str, track_id: int) -> str:
        return f"pipeline:semantic:{camera_id}:track:{track_id}"

    def _event_key(self, camera_id: str, event_type: str, rule_id: str) -> str:
        return f"pipeline:semantic:{camera_id}:event:{rule_id}:{event_type}"

    def get_track_analysis(self, camera_id: str, track_id: int) -> Optional[Dict[str, Any]]:
        try:
            raw = self._redis.get(self._track_key(camera_id, track_id))
            return json.loads(raw) if raw else None
        except Exception:
            return None

    def should_call_llm(
        self,
        camera_id: str,
        track_id: Optional[int],
        state_signature: str,
        cooldown_seconds: int,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        if track_id is None:
            return True, None
        cached = self.get_track_analysis(camera_id, track_id)
        if not cached:
            return True, None
        if cached.get("signature") == state_signature:
            age = time.time() - float(cached.get("updated_at", 0))
            if age < cooldown_seconds:
                return False, cached
        return True, cached

    def store(
        self,
        camera_id: str,
        track_id: Optional[int],
        signature: str,
        analysis: Dict[str, Any],
        ttl: int = 3600,
    ) -> None:
        if track_id is None:
            return
        payload = {
            "signature": signature,
            "analysis": analysis,
            "updated_at": time.time(),
        }
        try:
            self._redis.setex(self._track_key(camera_id, track_id), ttl, json.dumps(payload))
        except Exception:
            pass

    def build_signature(
        self,
        track_id: Optional[int],
        object_class: str,
        zone: str,
        event_type: str,
        det_count: int,
    ) -> str:
        return f"{track_id}|{object_class}|{zone}|{event_type}|{det_count}"


semantic_cache = SemanticCache()
