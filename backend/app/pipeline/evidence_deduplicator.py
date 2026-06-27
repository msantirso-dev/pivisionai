"""Suppress duplicate evidence screenshots."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional, Tuple

import redis

from app.config import get_settings
from app.pipeline.image_utils import compute_phash, phash_distance


@dataclass
class SnapshotDecision:
    save_new_file: bool
    reason: str
    reuse_path: Optional[str] = None


class EvidenceDeduplicator:
    def __init__(self):
        self._redis = redis.from_url(get_settings().redis_url, decode_responses=True)

    def _phash_key(self, camera_id: str, zone: str = "global") -> str:
        return f"pipeline:evidence:phash:{camera_id}:{zone}"

    def _meta_key(self, camera_id: str, zone: str = "global") -> str:
        return f"pipeline:evidence:meta:{camera_id}:{zone}"

    def decide(
        self,
        camera_id: str,
        jpeg_bytes: bytes,
        threshold: int,
        zone: str = "global",
    ) -> Tuple[SnapshotDecision, int]:
        """Return snapshot decision and pHash for the frame."""
        import cv2
        import numpy as np

        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return SnapshotDecision(save_new_file=True, reason="decode_failed"), 0

        ph = compute_phash(frame)
        try:
            meta_raw = self._redis.get(self._meta_key(camera_id, zone))
            if meta_raw:
                meta = json.loads(meta_raw)
                prev_ph = int(meta.get("phash", -1))
                prev_path = meta.get("path")
                if (
                    prev_ph >= 0
                    and phash_distance(ph, prev_ph) <= threshold
                    and prev_path
                    and os.path.exists(prev_path)
                ):
                    return (
                        SnapshotDecision(
                            save_new_file=False,
                            reason="duplicate_phash",
                            reuse_path=prev_path,
                        ),
                        ph,
                    )
            return SnapshotDecision(save_new_file=True, reason="new"), ph
        except Exception:
            return SnapshotDecision(save_new_file=True, reason="redis_unavailable"), ph

    def register_saved(self, camera_id: str, zone: str, filepath: str, phash: int) -> None:
        try:
            payload = json.dumps({"phash": phash, "path": filepath})
            self._redis.setex(self._meta_key(camera_id, zone), 3600, payload)
            self._redis.setex(self._phash_key(camera_id, zone), 3600, str(phash))
        except Exception:
            pass

    def should_save(self, camera_id: str, jpeg_bytes: bytes, threshold: int, zone: str = "global") -> Tuple[bool, str]:
        """Backward-compatible helper."""
        decision, _ = self.decide(camera_id, jpeg_bytes, threshold, zone)
        return decision.save_new_file, decision.reason


evidence_deduplicator = EvidenceDeduplicator()
