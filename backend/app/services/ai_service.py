"""YOLO-based AI detection service."""

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

YOLO_CLASSES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
    14: "bird",
    15: "cat",
    16: "dog",
    17: "horse",
    24: "backpack",
    26: "handbag",
    28: "suitcase",
}


@dataclass
class Detection:
    class_name: str
    confidence: float
    bbox: Tuple[int, int, int, int]
    track_id: Optional[int] = None
    center: Tuple[int, int] = field(default_factory=lambda: (0, 0))

    def __post_init__(self):
        x1, y1, x2, y2 = self.bbox
        self.center = ((x1 + x2) // 2, (y1 + y2) // 2)


class AIService:
    _model = None
    _trackers: Dict[str, dict] = {}

    def _get_model(self):
        if self._model is None:
            try:
                from ultralytics import YOLO

                model_path = settings.ai_model
                self._model = YOLO(model_path)
                logger.info("YOLO model loaded: %s on %s", model_path, settings.ai_device)
            except Exception as e:
                logger.error("Failed to load YOLO model: %s", e)
                raise
        return self._model

    def detect(
        self,
        frame: np.ndarray,
        confidence: float = None,
        min_object_size: int = None,
        target_classes: List[str] = None,
    ) -> List[Detection]:
        confidence = confidence or settings.ai_confidence
        min_object_size = min_object_size or settings.ai_min_object_size
        target_classes = target_classes or ["person", "car", "motorcycle", "bicycle", "truck", "bus"]

        model = self._get_model()
        h, w = frame.shape[:2]

        if w > settings.ai_analysis_width:
            scale = settings.ai_analysis_width / w
            new_w = settings.ai_analysis_width
            new_h = int(h * scale)
            frame_resized = cv2.resize(frame, (new_w, new_h))
            scale_x = w / new_w
            scale_y = h / new_h
        else:
            frame_resized = frame
            scale_x = scale_y = 1.0

        results = model(frame_resized, conf=confidence, verbose=False, device=settings.ai_device)
        detections = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls[0])
                class_name = YOLO_CLASSES.get(cls_id, f"class_{cls_id}")
                if class_name not in target_classes:
                    continue

                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                x1, y1, x2, y2 = int(x1 * scale_x), int(y1 * scale_y), int(x2 * scale_x), int(y2 * scale_y)

                obj_w, obj_h = x2 - x1, y2 - y1
                if obj_w < min_object_size or obj_h < min_object_size:
                    continue

                detections.append(
                    Detection(
                        class_name=class_name,
                        confidence=conf,
                        bbox=(x1, y1, x2, y2),
                    )
                )

        return detections

    def assign_track_ids(self, camera_id: str, detections: List[Detection]) -> List[Detection]:
        """Simple centroid tracking for MVP."""
        if camera_id not in self._trackers:
            self._trackers[camera_id] = {"next_id": 1, "tracks": {}}

        tracker = self._trackers[camera_id]
        used_ids = set()
        max_dist = 80

        for det in detections:
            best_id = None
            best_dist = max_dist
            for track_id, (cx, cy) in tracker["tracks"].items():
                if track_id in used_ids:
                    continue
                dist = ((det.center[0] - cx) ** 2 + (det.center[1] - cy) ** 2) ** 0.5
                if dist < best_dist:
                    best_dist = dist
                    best_id = track_id

            if best_id is not None:
                det.track_id = best_id
                used_ids.add(best_id)
                tracker["tracks"][best_id] = det.center
            else:
                det.track_id = tracker["next_id"]
                tracker["tracks"][det.track_id] = det.center
                tracker["next_id"] += 1

        return detections

    def draw_detections(self, frame: np.ndarray, detections: List[Detection]) -> np.ndarray:
        output = frame.copy()
        colors = {"person": (0, 255, 0), "car": (255, 0, 0), "default": (0, 165, 255)}

        for det in detections:
            color = colors.get(det.class_name, colors["default"])
            x1, y1, x2, y2 = det.bbox
            cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
            label = f"{det.class_name} {det.confidence:.2f}"
            if det.track_id:
                label += f" ID:{det.track_id}"
            cv2.putText(output, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        return output


ai_service = AIService()
