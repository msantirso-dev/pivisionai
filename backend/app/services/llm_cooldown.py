"""Redis-backed cooldown for LLM image descriptions per rule."""

import logging

import redis

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _redis_client():
    return redis.from_url(settings.redis_url, decode_responses=True)


def _cooldown_key(rule_id: str) -> str:
    return f"llm_describe:rule:{rule_id}"


def should_describe_rule(rule_id: str, cooldown_seconds: int | None = None) -> bool:
    """True if LLM description is allowed (first time or cooldown expired)."""
    if not rule_id:
        return False
    try:
        client = _redis_client()
        return not client.exists(_cooldown_key(str(rule_id)))
    except Exception as e:
        logger.warning("LLM cooldown check failed, allowing describe: %s", e)
        return True


def try_acquire_describe_slot(rule_id: str, cooldown_seconds: int | None = None) -> bool:
    """Atomically claim LLM describe slot for this rule (cooldown starts now)."""
    if not rule_id:
        return False
    ttl = cooldown_seconds or settings.llm_describe_cooldown_seconds
    try:
        client = _redis_client()
        return bool(client.set(_cooldown_key(str(rule_id)), "1", nx=True, ex=ttl))
    except Exception as e:
        logger.warning("LLM cooldown acquire failed, allowing describe: %s", e)
        return True


def release_describe_slot(rule_id: str) -> None:
    """Release slot so the next event can retry LLM describe (e.g. after failure)."""
    if not rule_id:
        return
    try:
        client = _redis_client()
        client.delete(_cooldown_key(str(rule_id)))
    except Exception as e:
        logger.warning("LLM cooldown release failed: %s", e)


def mark_rule_described(rule_id: str, cooldown_seconds: int | None = None) -> None:
    """Refresh cooldown TTL after a successful LLM description."""
    if not rule_id:
        return
    ttl = cooldown_seconds or settings.llm_describe_cooldown_seconds
    try:
        client = _redis_client()
        client.setex(_cooldown_key(str(rule_id)), ttl, "1")
    except Exception as e:
        logger.warning("LLM cooldown mark failed: %s", e)
