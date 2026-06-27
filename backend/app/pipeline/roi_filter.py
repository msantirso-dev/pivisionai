"""ROI zone filtering."""

from __future__ import annotations

from typing import List, Tuple

import cv2
import numpy as np

from app.pipeline.camera_config import CameraPipelineConfig, ROIZone


def point_in_polygon(point: Tuple[int, int], polygon: List[List[int]]) -> bool:
    if len(polygon) < 3:
        return True
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


class ROIFilter:
    def motion_in_roi(self, frame: np.ndarray, motion_mask_area: int, config: CameraPipelineConfig) -> bool:
        zones = config.roi_zones
        if not zones or all(len(z.polygon) < 3 for z in zones):
            return motion_mask_area >= config.min_motion_area

        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        total = 0
        for zone in zones:
            if len(zone.polygon) < 3:
                continue
            poly = np.array(zone.polygon, dtype=np.int32)
            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.fillPoly(mask, [poly], 255)
            diff = cv2.absdiff(gray, cv2.GaussianBlur(gray, (5, 5), 0))
            _, th = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
            total += int(cv2.countNonZero(cv2.bitwise_and(th, mask)))
        return total >= config.min_motion_area

    def center_in_roi(self, center: Tuple[int, int], config: CameraPipelineConfig) -> bool:
        zones = [z for z in config.roi_zones if len(z.polygon) >= 3]
        if not zones:
            return True
        return any(point_in_polygon(center, z.polygon) for z in zones)


roi_filter = ROIFilter()
