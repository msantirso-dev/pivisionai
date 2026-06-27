"""Helpers to build human-readable event reviews from LLM analysis."""

from typing import Any, Dict, Optional


def build_review_description(parsed: Optional[Dict[str, Any]], fallback: str = "") -> str:
    """Single-line description for events, Telegram and notifications."""
    if not parsed:
        return fallback

    parts = []
    summary = (parsed.get("summary") or "").strip()
    if summary:
        parts.append(summary)

    clothing = (parsed.get("person_clothing") or parsed.get("clothing") or "").strip()
    if clothing and clothing.lower() not in ("null", "none", "n/a", "no visible"):
        parts.append(f"Vestimenta: {clothing}")

    person_desc = (parsed.get("person_description") or "").strip()
    if person_desc and person_desc not in parts and person_desc != clothing:
        parts.append(person_desc)

    if not parts:
        scene = (parsed.get("scene_description") or "").strip()
        if scene:
            parts.append(scene)

    return " · ".join(parts) if parts else fallback


def review_details(parsed: Optional[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    if not parsed:
        return {"summary": None, "clothing": None, "scene": None, "context_match": None}

    clothing = parsed.get("person_clothing") or parsed.get("clothing")
    if isinstance(clothing, str) and clothing.strip().lower() in ("null", "none", "n/a"):
        clothing = None

    return {
        "summary": parsed.get("summary"),
        "clothing": clothing,
        "scene": parsed.get("scene_description"),
        "context_match": parsed.get("context_evaluation") or parsed.get("context_match"),
    }
