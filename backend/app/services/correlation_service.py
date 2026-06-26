"""IVS + AI event correlation service."""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

IVS_TO_CLASSES = {
    "tripwire": ["person", "car", "motorcycle", "bicycle", "truck"],
    "intrusion": ["person", "car", "motorcycle", "bicycle"],
    "motion_detect": ["person", "car", "motorcycle", "bicycle", "truck", "bus"],
    "people_counting": ["person"],
    "tamper": [],
    "video_loss": [],
}


def correlate_ivs_with_ai(
    dahua_event_type: str,
    detections: List,
    min_confidence: float = 0.4,
) -> Dict:
    """
    Validate a Dahua IVS event against AI detections.
    Returns correlation result with score and confirmation flag.
    """
    expected_classes = IVS_TO_CLASSES.get(dahua_event_type, ["person", "car"])
    if not expected_classes:
        return {
            "ai_confirmed": False,
            "correlation_score": 0.0,
            "matched_class": None,
            "reason": "event_type_not_validatable",
        }

    best_match = None
    best_confidence = 0.0

    for det in detections:
        if det.class_name in expected_classes and det.confidence >= min_confidence:
            if det.confidence > best_confidence:
                best_confidence = det.confidence
                best_match = det

    if best_match:
        score = min(best_confidence * 100, 100.0)
        return {
            "ai_confirmed": True,
            "correlation_score": round(score, 2),
            "matched_class": best_match.class_name,
            "matched_confidence": best_match.confidence,
            "track_id": best_match.track_id,
            "bbox": best_match.bbox,
            "reason": "ai_detection_confirms_ivs",
        }

    return {
        "ai_confirmed": False,
        "correlation_score": 0.0,
        "matched_class": None,
        "reason": "no_matching_detection",
    }


def should_discard_ivs(correlation: Dict, discard_unconfirmed: bool = True) -> bool:
    """Discard IVS events that AI cannot confirm when filter is enabled."""
    if not discard_unconfirmed:
        return False
    return not correlation.get("ai_confirmed", False)
