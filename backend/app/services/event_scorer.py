"""Event scoring and severity ranking."""

from datetime import datetime, timezone
from typing import Dict, Optional

from app.models import EventSeverity


def calculate_event_score(
    event_data: dict,
    rule: Optional[dict] = None,
    camera: Optional[dict] = None,
    repetition_count: int = 1,
) -> Dict:
    """Calculate automatic severity score for an event."""
    score = 0.0
    factors = {}

    severity_map = {
        EventSeverity.INFO.value: 10,
        EventSeverity.LOW.value: 25,
        EventSeverity.MEDIUM.value: 50,
        EventSeverity.HIGH.value: 75,
        EventSeverity.CRITICAL.value: 95,
    }

    base_severity = event_data.get("severity", EventSeverity.MEDIUM.value)
    severity_score = severity_map.get(base_severity, 50)
    score += severity_score * 0.3
    factors["rule_severity"] = severity_score

    object_class = event_data.get("object_class", "")
    if object_class == "person":
        score += 20
        factors["object_person"] = 20
    elif object_class in ("car", "truck", "bus", "motorcycle"):
        score += 15
        factors["object_vehicle"] = 15

    confidence = event_data.get("confidence", 0.5)
    score += confidence * 15
    factors["confidence"] = confidence * 15

    hour = datetime.now(timezone.utc).hour
    if 22 <= hour or hour < 6:
        score += 15
        factors["night_hours"] = 15

    if repetition_count > 1:
        rep_bonus = min(repetition_count * 5, 25)
        score += rep_bonus
        factors["repetition"] = rep_bonus

    if camera and camera.get("zone"):
        score += 5
        factors["zoned_camera"] = 5

    score = min(score, 100)

    if score >= 80:
        classification = "critical"
    elif score >= 60:
        classification = "operational_alert"
    else:
        classification = "informational"

    return {
        "score": round(score, 2),
        "classification": classification,
        "factors": factors,
    }


event_scorer = calculate_event_score
