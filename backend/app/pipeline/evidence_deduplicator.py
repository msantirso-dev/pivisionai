"""Suppress duplicate evidence screenshots."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import redis

from app.config import get_settings
from app.pipeline.image_utils import compute_phash, phash_distance


class EvidenceDeduplicator:
    def __init__(self):
        self._redis = redis.from_url(get_settings().redis_url, decode_responses=True)

    def _key(self, camera_id: str, zone: str = "global") -> str:
        return f"pipeline:evidence:phash:{camera_id}:{zone}"

    def should_save(self, camera_id: str, jpeg_bytes: bytes, threshold: int, zone: str = "global") -> Tuple[bool, str]:
        import cv2
        import numpy as np

        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return True, "decode_failed"
        ph = compute_phash(frame)
        key = self._key(camera_id, zone)
        try:
            prev = self._redis.get(key)
            if prev is not None and phash_distance(ph, int(prev)) <= threshold:
                return False, "duplicate_phash"
            self._redis.setex(key, 3600, str(ph))
            return True, "new"
        except Exception:
            return True, "redis_unavailable"


evidence_deduplicator = EvidenceDeduplicator()
