"""Notification channels configuration and tests."""

from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.core.dependencies import get_current_user, require_roles
from app.models import User, UserRole
from app.services.notification_service import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])
settings = get_settings()


@router.get("/config")
async def get_notifications_config(
    current_user: User = Depends(get_current_user),
):
    return {
        "telegram_configured": bool(settings.telegram_bot_token and settings.telegram_chat_id),
        "telegram_enabled": settings.telegram_enabled,
        "webhook_configured": bool(settings.webhook_default_url),
        "mqtt_configured": settings.mqtt_enabled,
        "channels": [
            {"id": "telegram", "label": "Telegram", "supports_snapshot": True},
            {"id": "webhook", "label": "Webhook", "supports_snapshot": False},
            {"id": "mqtt", "label": "MQTT", "supports_snapshot": False},
            {"id": "visual_alert", "label": "Panel web (tiempo real)", "supports_snapshot": False},
            {"id": "sound_alert", "label": "Alerta sonora (navegador)", "supports_snapshot": False},
        ],
    }


@router.post("/telegram/test")
async def test_telegram(
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPERVISOR])),
):
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN no configurado en .env")
    if not settings.telegram_chat_id:
        raise HTTPException(status_code=400, detail="TELEGRAM_CHAT_ID no configurado en .env")

    result = await notification_service.send_telegram(
        settings.telegram_chat_id,
        "✅ PI Vision AI — conexión Telegram OK.\nRecibirás capturas cuando una regla tenga Telegram activado.",
    )
    if result.get("status") != "sent":
        raise HTTPException(status_code=502, detail=result.get("error") or result.get("reason") or "Error Telegram")
    return {"success": True, "message": "Mensaje de prueba enviado a Telegram"}
