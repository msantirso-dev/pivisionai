"""Track LLM token consumption (Redis-backed, shared across workers)."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import redis

from app.config import get_settings

logger = logging.getLogger(__name__)

TOTAL_KEY = "llm:usage:total"
REQUESTS_KEY = "llm:usage:requests"


def _redis():
    return redis.from_url(get_settings().redis_url, decode_responses=True)


def _daily_key(day: Optional[str] = None) -> str:
    day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"llm:usage:daily:{day}"


def extract_usage_from_response(provider: str, raw: Optional[Dict[str, Any]]) -> Dict[str, int]:
    """Parse token counts from provider API raw response."""
    if not raw:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    provider = (provider or "").lower()

    if provider == "openai":
        usage = raw.get("usage") or {}
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        total = int(usage.get("total_tokens") or prompt + completion)
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total,
        }

    if provider == "ollama":
        prompt = int(raw.get("prompt_eval_count") or 0)
        completion = int(raw.get("eval_count") or 0)
        if not completion:
            msg = raw.get("message") or {}
            completion = int(msg.get("eval_count") or 0)
        return {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
        }

    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def record_llm_usage(
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    source: str = "analysis",
) -> None:
    total = max(0, prompt_tokens) + max(0, completion_tokens)
    if total <= 0:
        return

    try:
        client = _redis()
        pipe = client.pipeline()
        pipe.hincrby(TOTAL_KEY, "prompt_tokens", max(0, prompt_tokens))
        pipe.hincrby(TOTAL_KEY, "completion_tokens", max(0, completion_tokens))
        pipe.hincrby(TOTAL_KEY, "total_tokens", total)
        pipe.hincrby(TOTAL_KEY, "requests", 1)
        pipe.hincrby(REQUESTS_KEY, provider or "unknown", 1)

        daily = _daily_key()
        pipe.hincrby(daily, "prompt_tokens", max(0, prompt_tokens))
        pipe.hincrby(daily, "completion_tokens", max(0, completion_tokens))
        pipe.hincrby(daily, "total_tokens", total)
        pipe.hincrby(daily, "requests", 1)
        pipe.expire(daily, 60 * 60 * 24 * 45)
        pipe.execute()
    except Exception as exc:
        logger.warning("Failed to record LLM usage: %s", exc)


def _read_hash(key: str) -> Dict[str, int]:
    try:
        client = _redis()
        data = client.hgetall(key) or {}
        return {
            "prompt_tokens": int(data.get("prompt_tokens") or 0),
            "completion_tokens": int(data.get("completion_tokens") or 0),
            "total_tokens": int(data.get("total_tokens") or 0),
            "requests": int(data.get("requests") or 0),
        }
    except Exception as exc:
        logger.warning("Failed to read LLM usage: %s", exc)
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "requests": 0,
        }


def get_llm_usage_stats() -> Dict[str, Any]:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = _read_hash(TOTAL_KEY)
    today_stats = _read_hash(_daily_key(today))

    by_provider: Dict[str, int] = {}
    try:
        client = _redis()
        by_provider = {
            k: int(v) for k, v in (client.hgetall(REQUESTS_KEY) or {}).items()
        }
    except Exception:
        pass

    return {
        "total": total,
        "today": {**today_stats, "date": today},
        "by_provider": by_provider,
    }
