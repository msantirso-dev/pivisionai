"""Notification channels configuration and tests."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.dependencies import get_current_user, require_roles
from app.database import get_db
from app.models import User, UserRole
from app.services.notification_service import notification_service
from app.services.telegram_config import load_telegram_config, public_config, save_telegram_config

router = APIRouter(prefix="/notifications", tags=["Notifications"])
settings = get_settings()


class TelegramConfigUpdate(BaseModel):
    enabled: bool | None = None
    bot_token: str | None = None
    chat_id: str | None = None


@router.get("/config")
async def get_notifications_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tg = await load_telegram_config(db)
    tg_public = public_config(tg)
    return {
        "telegram": tg_public,
        "telegram_configured": tg_public["configured"],
        "telegram_enabled": tg_public["enabled"],
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


@router.get("/telegram/config")
async def get_telegram_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPERVISOR])),
):
    cfg = await load_telegram_config(db)
    return public_config(cfg)


@router.put("/telegram/config")
async def update_telegram_config(
    data: TelegramConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN])),
):
    updates = data.model_dump(exclude_unset=True)
    cfg = await save_telegram_config(db, updates)
    await db.commit()
    return public_config(cfg)


@router.post("/telegram/test")
async def test_telegram(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles([UserRole.ADMIN, UserRole.SUPERVISOR])),
):
    cfg = await load_telegram_config(db)
    public = public_config(cfg)
    if not public["configured"]:
        raise HTTPException(
            status_code=400,
            detail="Configure bot_token y chat_id en Integraciones → Telegram",
        )
    if not public["enabled"]:
        raise HTTPException(status_code=400, detail="Telegram está deshabilitado")

    result = await notification_service.send_telegram(
        cfg["chat_id"],
        "✅ PI Vision AI — conexión Telegram OK.\nRecibirás capturas cuando una regla tenga Telegram activado.",
        bot_token=cfg.get("bot_token"),
    )
    if result.get("status") != "sent":
        raise HTTPException(status_code=502, detail=result.get("error") or result.get("reason") or "Error Telegram")
    return {"success": True, "message": "Mensaje de prueba enviado a Telegram"}
