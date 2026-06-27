"""Unit tests for event-driven pipeline gates."""

from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from app.pipeline.camera_config import CameraPipelineConfig
from app.pipeline.evidence_deduplicator import EvidenceDeduplicator
from app.pipeline.image_utils import compute_phash, compute_ssim_proxy, phash_distance
from app.pipeline.preprocessor import OpenCVPreprocessor
from app.pipeline.semantic_cache import SemanticCache
from app.pipeline.stream_selector import StreamSelector


def _blank_frame(w: int = 640, h: int = 480, color=(128, 128, 128)) -> np.ndarray:
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[:] = color
    return frame


def _pattern_frame(w: int = 640, h: int = 480, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, (h, w, 3), dtype=np.uint8)


def test_phash_identical_frames():
    a = _blank_frame()
    b = _blank_frame()
    assert phash_distance(compute_phash(a), compute_phash(b)) == 0


def test_phash_different_frames():
    a = _pattern_frame(seed=1)
    b = _pattern_frame(seed=2)
    assert phash_distance(compute_phash(a), compute_phash(b)) > 0


def test_ssim_proxy_identical():
    a = _pattern_frame(seed=3)
    b = a.copy()
    assert compute_ssim_proxy(a, b) >= 0.99


def test_evidence_deduplicator_blocks_duplicate():
    dedup = EvidenceDeduplicator()
    dedup._redis = MagicMock()
    dedup._redis.get.return_value = None

    frame = _pattern_frame(seed=10)
    ok, enc = cv2.imencode(".jpg", frame)
    assert ok
    jpeg = enc.tobytes()

    decision, _ = dedup.decide("cam-1", jpeg, threshold=8)
    assert decision.save_new_file is True
    assert decision.reason == "new"

    dedup.register_saved("cam-1", "global", "/data/storage/snapshots/test.jpg", compute_phash(frame))

    import json

    dedup._redis.get.return_value = json.dumps(
        {"phash": compute_phash(frame), "path": "/data/storage/snapshots/test.jpg"}
    )

    with patch("app.pipeline.evidence_deduplicator.os.path.exists", return_value=True):
        decision2, _ = dedup.decide("cam-1", jpeg, threshold=8)
    assert decision2.save_new_file is False
    assert decision2.reason == "duplicate_phash"
    assert decision2.reuse_path == "/data/storage/snapshots/test.jpg"


def test_motion_gate_discards_static_frame():
    pre = OpenCVPreprocessor()
    cfg = CameraPipelineConfig(min_motion_area=500, use_mog2=True)
    frame = _pattern_frame(seed=4)
    for _ in range(5):
        pre.motion_area("cam-static", frame, cfg)
    area = pre.motion_area("cam-static", frame.copy(), cfg)
    assert area < cfg.min_motion_area


def test_motion_gate_detects_change():
    pre = OpenCVPreprocessor()
    cfg = CameraPipelineConfig(min_motion_area=100, use_mog2=True)
    pre.motion_area("cam-motion", _blank_frame(), cfg)
    moved = _blank_frame()
    cv2.rectangle(moved, (200, 150), (400, 350), (255, 255, 255), -1)
    area = pre.motion_area("cam-motion", moved, cfg)
    assert area >= cfg.min_motion_area


def test_preprocessor_duplicate_ssim():
    pre = OpenCVPreprocessor()
    cfg = CameraPipelineConfig(ssim_threshold=0.92, phash_threshold=0)
    frame = _blank_frame()
    dup, _ = pre.is_duplicate("cam-dup", frame, cfg)
    assert dup is False
    dup2, reason = pre.is_duplicate("cam-dup", frame.copy(), cfg)
    assert dup2 is True
    assert reason in ("ssim", "phash", "histogram")


def test_stream_selector_hybrid_uses_sub():
    sel = StreamSelector()
    sel._redis = MagicMock()
    sel._redis.get.return_value = "sub"
    cfg = CameraPipelineConfig(stream_mode="hybrid")
    assert sel.select("cam-1", cfg, important_event=False) == "sub"


def test_stream_selector_hybrid_event_uses_main():
    sel = StreamSelector()
    sel._redis = MagicMock()
    cfg = CameraPipelineConfig(stream_mode="hybrid")
    with patch("app.pipeline.stream_selector.metrics_service") as mock_metrics:
        choice = sel.select("cam-1", cfg, important_event=True)
    assert choice == "main"
    mock_metrics.increment.assert_called()


def test_stream_selector_auto_recommendation():
    sel = StreamSelector()
    sel._redis = MagicMock()
    sel._redis.get.return_value = "main"
    cfg = CameraPipelineConfig(stream_mode="auto")
    assert sel.select("cam-2", cfg) == "main"


def test_semantic_cache_skips_repeat_state():
    cache = SemanticCache()
    cache._redis = MagicMock()
    cache._redis.get.return_value = None

    sig = cache.build_signature(7, "person", "zone-a", "zone_intrusion", 1)
    call, cached = cache.should_call_llm("cam-1", 7, sig, cooldown_seconds=60)
    assert call is True
    assert cached is None

    cache.store("cam-1", 7, sig, {"summary": "person in zone"})
    cache._redis.get.return_value = cache._redis.setex.call_args[0][2]

    call2, cached2 = cache.should_call_llm("cam-1", 7, sig, cooldown_seconds=60)
    assert call2 is False
    assert cached2 is not None
