"""Decide when LLM analysis is warranted."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from app.pipeline.camera_config import CameraPipelineConfig
from app.pipeline.metrics import metrics_service
from app.pipeline.semantic_cache import semantic_cache

MINIMAL_LLM_PROMPT = """Analizá la imagen de seguridad. Respondé SOLO JSON válido:
{
  "action": "reuse|update|alert",
  "changed": true,
  "event_type": "",
  "priority": "low|medium|high|critical",
  "summary": "",
  "reason": ""
}
Reglas: action=reuse si no hay cambio relevante; update si cambió estado; alert si requiere operador."""


def should_invoke_llm(
    camera_id: str,
    config: CameraPipelineConfig,
    triggered: dict,
    detections_count: int,
    prior_cached: Optional[Dict] = None,
) -> Tuple[bool, str]:
    if not config.llm_enabled:
        metrics_service.increment(camera_id, "llm_calls_avoided_total")
        return False, "llm_disabled_camera"

    event_type = triggered.get("event_type", "")
    track_id = triggered.get("track_id")
    rule_id = str(triggered.get("rule_id") or "none")
    signature = semantic_cache.build_signature(
        track_id,
        triggered.get("object_class", ""),
        rule_id,
        event_type,
        detections_count,
    )

    call, cached = semantic_cache.should_call_llm(
        camera_id, track_id, signature, config.cooldown_seconds
    )
    if not call:
        metrics_service.increment(camera_id, "llm_calls_avoided_total")
        return False, "semantic_cache_hit"

    # Only on meaningful triggers
    meaningful = event_type in (
        "line_crossing",
        "zone_intrusion",
        "ivs_intrusion",
        "ivs_tripwire",
    ) or triggered.get("metadata", {}).get("force_llm")
    if not meaningful:
        metrics_service.increment(camera_id, "llm_calls_avoided_total")
        return False, "not_meaningful_event"

    metrics_service.increment(camera_id, "llm_calls_sent_total")
    return True, "invoke"


def apply_llm_gate_to_actions(triggered: dict, allow: bool) -> dict:
    actions = dict(triggered.get("actions") or {})
    if not allow:
        actions["llm_describe"] = False
    return actions
