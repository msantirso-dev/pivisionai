"""OpenCV motion and similarity gates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

from app.pipeline.camera_config import CameraPipelineConfig
from app.pipeline.image_utils import compute_phash, compute_ssim_proxy, histogram_similarity, phash_distance


@dataclass
class PreprocessState:
    mog2: Optional[cv2.BackgroundSubtractorMOG2] = None
    knn: Optional[cv2.BackgroundSubtractorKNN] = None
    prev_gray: Optional[np.ndarray] = None
    prev_phash: Optional[int] = None
    prev_frame: Optional[np.ndarray] = None


class OpenCVPreprocessor:
    def __init__(self):
        self._states: Dict[str, PreprocessState] = {}

    def _state(self, camera_id: str) -> PreprocessState:
        if camera_id not in self._states:
            self._states[camera_id] = PreprocessState(
                mog2=cv2.createBackgroundSubtractorMOG2(history=120, varThreshold=16, detectShadows=False),
                knn=cv2.createBackgroundSubtractorKNN(history=120, dist2Threshold=400.0, detectShadows=False),
            )
        return self._states[camera_id]

    def resize_for_analysis(self, frame: np.ndarray, target: int) -> np.ndarray:
        h, w = frame.shape[:2]
        if max(h, w) <= target:
            return frame
        scale = target / max(h, w)
        return cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    def motion_area(self, camera_id: str, frame: np.ndarray, config: CameraPipelineConfig) -> int:
        state = self._state(camera_id)
        fg = None
        if config.use_mog2 and state.mog2 is not None:
            fg = state.mog2.apply(frame)
        elif config.use_knn and state.knn is not None:
            fg = state.knn.apply(frame)
        else:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if state.prev_gray is not None:
                diff = cv2.absdiff(state.prev_gray, gray)
                _, fg = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
            state.prev_gray = gray

        if fg is None:
            return 0

        if config.use_optical_flow and state.prev_gray is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            flow = cv2.calcOpticalFlowFarneback(state.prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            motion_from_flow = int(np.sum(mag > 2.0))
            if motion_from_flow > config.min_motion_area:
                return motion_from_flow

        _, thresh = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return sum(int(cv2.contourArea(c)) for c in contours if cv2.contourArea(c) >= 50)

    def is_duplicate(self, camera_id: str, frame: np.ndarray, config: CameraPipelineConfig) -> Tuple[bool, str]:
        state = self._state(camera_id)
        ph = compute_phash(frame)
        if state.prev_phash is not None and phash_distance(ph, state.prev_phash) <= config.phash_threshold:
            return True, "phash"

        if state.prev_frame is not None:
            ssim = compute_ssim_proxy(state.prev_frame, frame)
            if ssim >= config.ssim_threshold:
                return True, "ssim"
            hist = histogram_similarity(state.prev_frame, frame)
            if hist >= config.histogram_threshold:
                return True, "histogram"

        state.prev_phash = ph
        state.prev_frame = frame.copy()
        return False, ""


opencv_preprocessor = OpenCVPreprocessor()
