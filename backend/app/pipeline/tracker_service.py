"""Fix tracker service - clean implementation."""

from __future__ import annotations

import logging
from typing import List, Optional

from app.config import get_settings
from app.pipeline.camera_config import CameraPipelineConfig
from app.services.ai_service import TARGET_CLASSES, Detection, ai_service

logger = logging.getLogger(__name__)


class TrackerService:
    def detect_and_track(
        self,
        camera_id: str,
        frame,
        config: CameraPipelineConfig,
        confidence: float,
        min_object_size: int,
    ) -> List[Detection]:
        if config.tracker == "bytetrack":
            tracked = self._bytetrack(frame, confidence, min_object_size)
            if tracked is not None:
                return tracked
        detections = ai_service.detect(frame, confidence=confidence, min_object_size=min_object_size)
        return ai_service.assign_track_ids(camera_id, detections, frame_width=frame.shape[1])

    def _bytetrack(self, frame, confidence: float, min_object_size: int) -> Optional[List[Detection]]:
        try:
            model = ai_service._get_model()
            results = model.track(
                frame,
                conf=confidence,
                persist=True,
                tracker="bytetrack.yaml",
                verbose=False,
                device=get_settings().ai_device,
            )
            detections: List[Detection] = []
            names = model.names or {}
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue
                for box in boxes:
                    cls_id = int(box.cls[0])
                    class_name = names.get(cls_id, f"class_{cls_id}")
                    if class_name not in TARGET_CLASSES:
                        continue
                    x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                    if (x2 - x1) < min_object_size or (y2 - y1) < min_object_size:
                        continue
                    tid = int(box.id[0]) if box.id is not None else None
                    detections.append(
                        Detection(
                            class_name=class_name,
                            confidence=float(box.conf[0]),
                            bbox=(x1, y1, x2, y2),
                            track_id=tid,
                        )
                    )
            return detections
        except Exception as exc:
            logger.debug("ByteTrack unavailable, fallback to centroid: %s", exc)
            return None


tracker_service = TrackerService()
