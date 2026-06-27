"""Telegram bot configuration: env defaults + DB override."""

import logging
from typing import Any, Dict, Optional

from sqlalchemy import select

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

TELEGRAM_INTEGRATION_TYPE = "telegram"


def config_from_env() -> Dict[str, Any]:
    return {
        "enabled": settings.telegram_enabled,
        "bot_token": settings.telegram_bot_token,
        "chat_id": settings.telegram_chat_id,
    }


def mask_bot_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 10:
        return "****"
    return f"{token[:6]}...{token[-4:]}"


def public_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    token = cfg.get("bot_token", "")
    chat_id = cfg.get("chat_id", "")
    return {
        "enabled": bool(cfg.get("enabled")),
        "bot_token_set": bool(token),
        "bot_token_masked": mask_bot_token(token),
        "chat_id": chat_id or "",
        "configured": bool(token and chat_id),
        "source": cfg.get("_source", "env"),
    }


async def load_telegram_config(session=None) -> Dict[str, Any]:
    cfg = config_from_env()
    cfg["_source"] = "env"
    try:
        if session is None:
            from app.database import AsyncSessionLocal

            async with AsyncSessionLocal() as s:
                return await _merge_db_config(s, cfg)
        return await _merge_db_config(session, cfg)
    except Exception as exc:
        logger.warning("Telegram config DB load failed, using env: %s", exc)
        return cfg


async def _merge_db_config(session, cfg: Dict[str, Any]) -> Dict[str, Any]:
    from app.models import Integration

    result = await session.execute(
        select(Integration).where(
            Integration.integration_type == TELEGRAM_INTEGRATION_TYPE,
            Integration.is_active == True,
        )
    )
    row = result.scalar_one_or_none()
    if row and row.config:
        merged = {**cfg, **row.config}
        if not row.config.get("bot_token") and cfg.get("bot_token"):
            merged["bot_token"] = cfg["bot_token"]
        merged["_source"] = "database"
        return merged
    return cfg


async def save_telegram_config(session, updates: Dict[str, Any]) -> Dict[str, Any]:
    from app.models import Integration

    current = await load_telegram_config(session)
    if updates.get("bot_token") in ("", None) and current.get("bot_token"):
        updates.pop("bot_token", None)

    new_cfg = {**current, **{k: v for k, v in updates.items() if v is not None}}
    for key in ("_source",):
        new_cfg.pop(key, None)

    db_cfg = {
        "enabled": new_cfg.get("enabled", False),
        "bot_token": new_cfg.get("bot_token", ""),
        "chat_id": new_cfg.get("chat_id", ""),
    }

    result = await session.execute(
        select(Integration).where(Integration.integration_type == TELEGRAM_INTEGRATION_TYPE)
    )
    row = result.scalar_one_or_none()
    if row:
        row.config = db_cfg
        row.is_active = True
        row.name = "Telegram Bot"
    else:
        session.add(
            Integration(
                name="Telegram Bot",
                integration_type=TELEGRAM_INTEGRATION_TYPE,
                config=db_cfg,
                is_active=True,
            )
        )
    await session.flush()
    saved = await load_telegram_config(session)
    return saved


def resolve_telegram_credentials(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Sync helper when async load is unavailable."""
    base = config_from_env()
    if cfg:
        base.update(cfg)
    return {
        "enabled": bool(base.get("enabled")),
        "bot_token": base.get("bot_token") or "",
        "chat_id": base.get("chat_id") or "",
    }
