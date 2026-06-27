"""Resolve and capture camera streams."""

from __future__ import annotations

from typing import Literal, Optional, Tuple

import numpy as np

from app.pipeline.camera_config import CameraPipelineConfig
from app.services.camera_capture import capture_frame_np
from app.services.rtsp_service import resolve_camera_rtsp_urls, rtsp_service

StreamKind = Literal["main", "sub", "http"]


class StreamManager:
    def resolve_urls(self, camera, config: CameraPipelineConfig) -> Tuple[str, Optional[str]]:
        main = config.main_stream_url or None
        sub = config.sub_stream_url or None
        if not main or not sub:
            built_main, built_sub = resolve_camera_rtsp_urls(camera)
            main = main or built_main
            sub = sub or built_sub
        return main or "", sub

    def capture(
        self,
        camera,
        config: CameraPipelineConfig,
        stream: StreamKind,
        force_event: bool = False,
    ) -> Tuple[Optional[np.ndarray], int, int, str, int]:
        """Returns frame, w, h, source, bytes_estimate."""
        if stream == "http" or getattr(camera, "connection_mode", "local") == "cloud":
            frame, w, h, source = capture_frame_np(camera)
            if frame is None:
                return None, 0, 0, source or "", 0
            return frame, w, h, source, frame.nbytes

        main, sub = self.resolve_urls(camera, config)
        url = main if stream == "main" else (sub or main)
        if not url:
            frame, w, h, source = capture_frame_np(camera)
            if frame is None:
                return None, 0, 0, "", 0
            return frame, w, h, source, frame.nbytes

        frame = rtsp_service.read_frame(url)
        if frame is None:
            return None, 0, 0, f"rtsp_{stream}", 0
        h, w = frame.shape[:2]
        return frame, w, h, f"rtsp_{stream}", frame.nbytes


stream_manager = StreamManager()
