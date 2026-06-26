"""Quick detection test for a camera."""
import asyncio
import sys

from app.services.ai_service import ai_service
from app.services.camera_capture import capture_frame_np
from app.services.camera_db import get_camera
from app.services.rule_engine import rule_engine
from app.workers.tasks import scale_geometry


async def main(camera_id: str):
    cam = await get_camera(camera_id)
    if not cam:
        print("Camera not found")
        return

    frame, w, h, src = capture_frame_np(cam)
    print(f"Camera: {cam.name} | frame: {w}x{h} | source: {src}")
    if frame is None:
        print("NO FRAME")
        return

    for conf in (0.45, 0.35, 0.25, 0.15):
        dets = ai_service.detect(frame, confidence=conf, min_object_size=10)
        summary = [(d.class_name, round(d.confidence, 2), d.bbox) for d in dets[:8]]
        print(f"  conf={conf}: {len(dets)} detections -> {summary}")

    dets = ai_service.detect(frame, confidence=0.25, min_object_size=10)
    dets = ai_service.assign_track_ids(str(cam.id), dets)
    geo = {
        "polygon": [[10, 10], [630, 10], [630, 350], [10, 350]],
        "reference_size": {"width": 640, "height": 360},
    }
    scaled = scale_geometry(geo, w, h)
    rules = [
        {
            "id": "test",
            "name": "Personas",
            "rule_type": "zone_intrusion",
            "object_classes": ["person"],
            "min_confidence": 0.25,
            "is_active": True,
            "geometry": scaled,
            "severity": "medium",
            "actions": {},
        }
    ]
    events = rule_engine.evaluate_rules(str(cam.id), dets, rules, {})
    print(f"Rule triggers: {len(events)}")


if __name__ == "__main__":
    cam_id = sys.argv[1] if len(sys.argv) > 1 else "1e7cafe1-4bd9-49e8-89d5-6ce00b033962"
    asyncio.run(main(cam_id))
