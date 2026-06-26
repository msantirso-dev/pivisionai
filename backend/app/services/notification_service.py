"""Notification service: Telegram, Webhook and MQTT."""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def format_event_caption(event: Dict[str, Any]) -> str:
    severity = (event.get("severity") or "medium").upper()
    lines = [
        "🚨 PI Vision AI",
        "",
        f"Cámara: {event.get('camera_name') or event.get('camera_id', 'N/A')}",
        f"Evento: {event.get('event_type', 'alerta')}",
        f"Objeto: {event.get('object_class') or '-'}",
    ]
    if event.get("confidence") is not None:
        lines.append(f"Confianza: {event.get('confidence'):.0%}")

    llm = (event.get("metadata") or {}).get("llm_analysis") or {}
    parsed = llm.get("parsed") or {}
    summary = parsed.get("summary") or llm.get("text")
    if summary:
        lines.extend(["", "📝 Análisis IA:", str(summary)[:600]])

    lines.extend([
        f"Criticidad: {severity}",
        "",
        event.get("description") or "Alerta de seguridad detectada",
    ])
    return "\n".join(lines)[:1024]


class NotificationService:
    async def send_telegram(
        self,
        chat_id: str,
        caption: str,
        photo_path: Optional[str] = None,
        bot_token: Optional[str] = None,
    ) -> Dict:
        token = bot_token or settings.telegram_bot_token
        if not token:
            return {"status": "skipped", "reason": "TELEGRAM_BOT_TOKEN no configurado"}
        if not chat_id:
            return {"status": "skipped", "reason": "chat_id no configurado"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if photo_path and os.path.exists(photo_path):
                    url = f"https://api.telegram.org/bot{token}/sendPhoto"
                    with open(photo_path, "rb") as photo_file:
                        response = await client.post(
                            url,
                            data={"chat_id": str(chat_id), "caption": caption},
                            files={"photo": ("alert.jpg", photo_file, "image/jpeg")},
                        )
                else:
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    response = await client.post(
                        url,
                        json={"chat_id": str(chat_id), "text": caption},
                    )

                data = response.json()
                if response.is_success and data.get("ok"):
                    return {"status": "sent", "message_id": data.get("result", {}).get("message_id")}

                return {
                    "status": "failed",
                    "status_code": response.status_code,
                    "error": data.get("description", response.text[:300]),
                }
        except Exception as e:
            logger.error("Telegram failed: %s", e)
            return {"status": "error", "error": str(e)}

    async def send_webhook(self, url: str, payload: Dict[str, Any]) -> Dict:
        if not url:
            return {"status": "skipped", "reason": "no url"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                return {
                    "status": "sent" if response.is_success else "failed",
                    "status_code": response.status_code,
                    "response": response.text[:500],
                }
        except Exception as e:
            logger.error("Webhook failed: %s", e)
            return {"status": "error", "error": str(e)}

    def send_mqtt(self, topic: str, payload: Dict[str, Any]) -> Dict:
        try:
            import paho.mqtt.client as mqtt

            broker_url = settings.mqtt_broker.replace("mqtt://", "").replace("mqtts://", "")
            host = broker_url.split(":")[0]
            port = int(broker_url.split(":")[1]) if ":" in broker_url else 1883

            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            if settings.mqtt_username:
                client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
            client.connect(host, port, 60)
            client.publish(topic or settings.mqtt_topic, json.dumps(payload), qos=1)
            client.disconnect()
            return {"status": "sent", "topic": topic or settings.mqtt_topic}
        except Exception as e:
            logger.error("MQTT failed: %s", e)
            return {"status": "error", "error": str(e)}

    async def notify_event(self, event: Dict[str, Any], actions: Dict[str, Any]) -> List[Dict]:
        results = []
        payload = {
            "event_id": str(event.get("id", "")),
            "camera_id": str(event.get("camera_id", "")),
            "camera_name": event.get("camera_name"),
            "event_type": event.get("event_type"),
            "severity": event.get("severity"),
            "object_class": event.get("object_class"),
            "description": event.get("description"),
            "confidence": event.get("confidence"),
            "occurred_at": event.get("occurred_at"),
            "snapshot_url": event.get("snapshot_url"),
            "metadata": event.get("metadata", {}),
        }
        caption = format_event_caption(event)

        if actions.get("telegram"):
            chat_id = actions.get("telegram_chat_id") or settings.telegram_chat_id
            photo_path = event.get("snapshot_path") if actions.get("send_snapshot", True) else None
            result = await self.send_telegram(chat_id, caption, photo_path)
            results.append({"channel": "telegram", **result})

        if actions.get("webhook"):
            url = actions.get("webhook_url") or settings.webhook_default_url
            if url:
                result = await self.send_webhook(url, payload)
                results.append({"channel": "webhook", **result})
            else:
                results.append({"channel": "webhook", "status": "skipped", "reason": "sin URL"})

        if actions.get("mqtt"):
            topic = actions.get("mqtt_topic") or settings.mqtt_topic
            result = self.send_mqtt(topic, payload)
            results.append({"channel": "mqtt", **result})

        if actions.get("visual_alert"):
            results.append({"channel": "visual_alert", "status": "queued"})

        if actions.get("sound_alert"):
            results.append({"channel": "sound_alert", "status": "queued"})

        return results


notification_service = NotificationService()
