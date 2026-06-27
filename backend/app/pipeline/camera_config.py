"""Per-camera pipeline configuration."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

StreamMode = Literal["main", "sub", "hybrid", "auto"]
LocationType = Literal["interior", "exterior", "perimetro", "acceso", "ptz"]


class ROIZone(BaseModel):
    name: str = "default"
    polygon: List[List[int]] = Field(default_factory=list)


class CameraPipelineConfig(BaseModel):
    main_stream_url: Optional[str] = None
    sub_stream_url: Optional[str] = None
    stream_mode: StreamMode = "hybrid"
    analysis_resolution: int = 640
    analysis_fps: float = 2.0
    detector_fps: float = 1.0
    llm_enabled: bool = True
    roi_zones: List[ROIZone] = Field(default_factory=list)
    location_type: LocationType = "exterior"
    min_motion_area: int = 500
    ssim_threshold: float = 0.92
    phash_threshold: int = 8
    cooldown_seconds: int = 30
    enable_ab_test: bool = False
    use_mog2: bool = True
    use_knn: bool = False
    use_optical_flow: bool = False
    histogram_threshold: float = 0.98
    tracker: Literal["bytetrack", "sort", "centroid"] = "bytetrack"
    pipeline_enabled: bool = True

    @classmethod
    def from_camera(cls, camera) -> "CameraPipelineConfig":
        raw = dict(getattr(camera, "metadata_", None) or {})
        pipeline = raw.get("pipeline_config") or {}
        merged: Dict[str, Any] = {
            "analysis_fps": getattr(camera, "ai_fps", 5) or 2.0,
            "llm_enabled": getattr(camera, "ai_enabled", True),
        }
        if getattr(camera, "analysis_mode", None) == "continuous":
            merged["pipeline_enabled"] = pipeline.get("pipeline_enabled", False)
        merged.update(pipeline)
        if camera.rtsp_main and not merged.get("main_stream_url"):
            merged.setdefault("main_stream_url", None)
        return cls.model_validate(merged)

    def to_storage(self) -> dict:
        return self.model_dump()


def save_pipeline_config(metadata: dict, config: CameraPipelineConfig) -> dict:
    meta = dict(metadata or {})
    meta["pipeline_config"] = config.to_storage()
    return meta
