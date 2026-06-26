"""Rule engine for line crossing, zone intrusion, and schedules."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from app.models import EventSeverity, RuleType
from app.services.ai_service import Detection

logger = logging.getLogger(__name__)


def point_in_polygon(point: Tuple[int, int], polygon: List[List[int]]) -> bool:
    x, y = point
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi):
            inside = not inside
        j = i
    return inside


def line_side(point: Tuple[int, int], line: Dict) -> float:
    """Returns signed distance from point to line (positive = one side, negative = other)."""
    x, y = point
    x1, y1 = line["start"]
    x2, y2 = line["end"]
    return (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)


def is_schedule_active(schedule: Optional[dict], now: Optional[datetime] = None) -> bool:
    if not schedule:
        return True

    now = now or datetime.now(timezone.utc)
    tz = ZoneInfo(schedule.get("timezone", "UTC"))
    local_now = now.astimezone(tz)
    day_name = local_now.strftime("%A").lower()
    current_time = local_now.strftime("%H:%M")

    weekly = schedule.get("weekly", {})
    day_slots = weekly.get(day_name, [])

    if not day_slots:
        return False

    for slot in day_slots:
        start = slot.get("start", "00:00")
        end = slot.get("end", "23:59")
        if start <= current_time <= end:
            return True

    return False


class RuleEngine:
    def __init__(self):
        self._track_history: Dict[str, Dict[int, List[Tuple[int, int]]]] = {}
        self._zone_presence: Dict[str, Dict[int, datetime]] = {}

    def evaluate_rules(
        self,
        camera_id: str,
        detections: List[Detection],
        rules: List[dict],
        schedule_map: Dict[str, dict],
    ) -> List[dict]:
        triggered = []
        cam_key = str(camera_id)

        if cam_key not in self._track_history:
            self._track_history[cam_key] = {}

        for det in detections:
            if det.track_id is None:
                continue

            track_id = det.track_id
            if track_id not in self._track_history[cam_key]:
                self._track_history[cam_key][track_id] = []
            self._track_history[cam_key][track_id].append(det.center)
            if len(self._track_history[cam_key][track_id]) > 30:
                self._track_history[cam_key][track_id] = self._track_history[cam_key][track_id][-30:]

        for rule in rules:
            if not rule.get("is_active", True):
                continue

            schedule = schedule_map.get(str(rule.get("schedule_id")))
            if schedule and not is_schedule_active(schedule):
                continue

            rule_type = rule.get("rule_type")
            object_classes = rule.get("object_classes", ["person", "car"])
            geometry = rule.get("geometry", {})

            for det in detections:
                if det.class_name not in object_classes:
                    continue
                if det.confidence < rule.get("min_confidence", 0.45):
                    continue

                event = None

                if rule_type == RuleType.LINE_CROSSING.value or rule_type == "line_crossing":
                    event = self._check_line_crossing(camera_id, det, rule, geometry)
                elif rule_type == RuleType.ZONE_INTRUSION.value or rule_type == "zone_intrusion":
                    event = self._check_zone_intrusion(camera_id, det, rule, geometry)

                if event:
                    triggered.append(event)

        return triggered

    def _check_line_crossing(
        self, camera_id: str, det: Detection, rule: dict, geometry: dict
    ) -> Optional[dict]:
        line = geometry.get("line")
        if not line:
            return None

        cam_key = str(camera_id)
        track_id = det.track_id
        if track_id is None:
            return None

        history = self._track_history.get(cam_key, {}).get(track_id, [])
        if len(history) < 2:
            return None

        prev_center = history[-2]
        curr_center = history[-1]

        prev_side = line_side(prev_center, line)
        curr_side = line_side(curr_center, line)

        if prev_side * curr_side < 0:
            direction = geometry.get("direction", "any")
            cross_direction = "forward" if curr_side > prev_side else "backward"

            if direction != "any" and direction != cross_direction:
                return None

            return {
                "rule_id": rule.get("id"),
                "rule_name": rule.get("name"),
                "context_description": rule.get("context_description") or "",
                "rule_type": "line_crossing",
                "event_type": "line_crossing",
                "severity": rule.get("severity", EventSeverity.MEDIUM.value),
                "object_class": det.class_name,
                "track_id": track_id,
                "confidence": det.confidence,
                "description": f"{det.class_name} cruzó línea '{rule.get('name')}' ({cross_direction})",
                "metadata": {
                    "bbox": det.bbox,
                    "direction": cross_direction,
                    "line": line,
                },
                "actions": rule.get("actions", {}),
            }
        return None

    def _check_zone_intrusion(
        self, camera_id: str, det: Detection, rule: dict, geometry: dict
    ) -> Optional[dict]:
        polygon = geometry.get("polygon")
        if not polygon:
            return None

        if not point_in_polygon(det.center, polygon):
            return None

        cam_key = str(camera_id)
        track_id = det.track_id
        zone_key = f"{cam_key}_{rule.get('id')}"

        if zone_key not in self._zone_presence:
            self._zone_presence[zone_key] = {}

        if track_id in self._zone_presence[zone_key]:
            return None

        self._zone_presence[zone_key][track_id] = datetime.now(timezone.utc)

        return {
            "rule_id": rule.get("id"),
            "rule_name": rule.get("name"),
            "context_description": rule.get("context_description") or "",
            "rule_type": "zone_intrusion",
            "event_type": "zone_intrusion",
            "severity": rule.get("severity", EventSeverity.MEDIUM.value),
            "object_class": det.class_name,
            "track_id": track_id,
            "confidence": det.confidence,
            "description": f"{det.class_name} ingresó a zona '{rule.get('name')}'",
            "metadata": {
                "bbox": det.bbox,
                "polygon": polygon,
                "center": det.center,
            },
            "actions": rule.get("actions", {}),
        }


rule_engine = RuleEngine()
