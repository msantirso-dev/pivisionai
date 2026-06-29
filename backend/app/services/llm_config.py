"""LLM configuration: env defaults + DB override."""

import logging
from typing import Any, Dict, Optional

from sqlalchemy import select

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

LLM_INTEGRATION_TYPE = "llm_vision"


def config_from_env() -> Dict[str, Any]:
    return {
        "enabled": settings.llm_enabled,
        "provider": settings.llm_provider,
        "analyze_on_event": settings.llm_analyze_on_event,
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "openai_api_key": settings.openai_api_key,
        "openai_model": settings.openai_model,
        "openai_base_url": settings.openai_base_url,
        "openrouter_api_key": settings.openrouter_api_key,
        "openrouter_model": settings.openrouter_model,
        "openrouter_base_url": settings.openrouter_base_url,
        "openrouter_site_url": settings.openrouter_site_url,
        "openrouter_app_name": settings.openrouter_app_name,
        "max_tokens": settings.llm_max_tokens,
        "system_prompt": settings.llm_system_prompt,
    }


def mask_api_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


def public_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Config safe for API responses (hide full API key)."""
    out = dict(cfg)
    openai_key = out.get("openai_api_key", "")
    out["openai_api_key_set"] = bool(openai_key)
    out["openai_api_key_masked"] = mask_api_key(openai_key)
    out.pop("openai_api_key", None)

    or_key = out.get("openrouter_api_key", "")
    out["openrouter_api_key_set"] = bool(or_key)
    out["openrouter_api_key_masked"] = mask_api_key(or_key)
    out.pop("openrouter_api_key", None)

    out["config_source"] = out.pop("_config_source", "env")
    out["effective_provider"] = out.get("provider") or "none"
    return out


async def load_llm_config(session=None) -> Dict[str, Any]:
    cfg = config_from_env()
    try:
        if session is None:
            from app.database import AsyncSessionLocal

            async with AsyncSessionLocal() as s:
                return await _merge_db_config(s, cfg)
        return await _merge_db_config(session, cfg)
    except Exception as e:
        logger.warning("LLM config DB load failed, using env: %s", e)
        return cfg


async def _merge_db_config(session, cfg: Dict[str, Any]) -> Dict[str, Any]:
    from app.models import Integration

    result = await session.execute(
        select(Integration).where(
            Integration.integration_type == LLM_INTEGRATION_TYPE,
            Integration.is_active == True,
        )
    )
    row = result.scalar_one_or_none()
    if row and row.config:
        merged = {**cfg, **row.config}
        if not row.config.get("openai_api_key") and cfg.get("openai_api_key"):
            merged["openai_api_key"] = cfg["openai_api_key"]
        if not row.config.get("openrouter_api_key") and cfg.get("openrouter_api_key"):
            merged["openrouter_api_key"] = cfg["openrouter_api_key"]
        merged["_config_source"] = "database"
        return merged
    cfg["_config_source"] = "env"
    return cfg


async def save_llm_config(session, updates: Dict[str, Any]) -> Dict[str, Any]:
    from app.models import Integration

    current = await load_llm_config(session)
    if updates.get("openai_api_key") in ("", None) and current.get("openai_api_key"):
        updates.pop("openai_api_key", None)
    if updates.get("openrouter_api_key") in ("", None) and current.get("openrouter_api_key"):
        updates.pop("openrouter_api_key", None)

    new_cfg = {**current, **{k: v for k, v in updates.items() if v is not None}}
    env_only = {"openai_api_key", "openrouter_api_key"}
    db_cfg = {k: v for k, v in new_cfg.items() if k not in env_only or v}

    result = await session.execute(
        select(Integration).where(Integration.integration_type == LLM_INTEGRATION_TYPE)
    )
    row = result.scalar_one_or_none()
    if row:
        row.config = db_cfg
        row.is_active = True
        row.name = "LLM Vision Config"
    else:
        session.add(
            Integration(
                name="LLM Vision Config",
                integration_type=LLM_INTEGRATION_TYPE,
                config=db_cfg,
                is_active=True,
            )
        )
    await session.flush()
    return new_cfg
