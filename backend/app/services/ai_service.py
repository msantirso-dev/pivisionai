"""YOLO-based AI detection service."""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

TARGET_CLASSES = ["person", "car", "motorcycle", "bicycle", "truck", "bus"]


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

    def _inference_imgsz(self, frame: np.ndarray) -> int:
        h, w = frame.shape[:2]
        longest = max(w, h)
        cap = getattr(settings, "ai_imgsz", 1280) or 1280
        return min(longest, cap)

    def detect(
        self,
        frame: np.ndarray,
        confidence: float = None,
        min_object_size: int = None,
        target_classes: List[str] = None,
    ) -> List[Detection]:
        confidence = confidence or settings.ai_confidence
        min_object_size = min_object_size or settings.ai_min_object_size
        target_classes = target_classes or TARGET_CLASSES

        model = self._get_model()
        imgsz = self._inference_imgsz(frame)

        results = model(
            frame,
            conf=confidence,
            imgsz=imgsz,
            verbose=False,
            device=settings.ai_device,
        )
        detections = []
        names = model.names or {}

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                cls_id = int(box.cls[0])
                class_name = names.get(cls_id, f"class_{cls_id}")
                if class_name not in target_classes:
                    continue

                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

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

        if detections:
            logger.info("YOLO detected %d objects (imgsz=%s, conf=%.2f)", len(detections), imgsz, confidence)

        return detections

    def assign_track_ids(self, camera_id: str, detections: List[Detection], frame_width: int = 1280) -> List[Detection]:
        """Simple centroid tracking for MVP."""
        if camera_id not in self._trackers:
            self._trackers[camera_id] = {"next_id": 1, "tracks": {}}

        tracker = self._trackers[camera_id]
        used_ids = set()
        max_dist = max(80, frame_width // 24)

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
        import cv2

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
