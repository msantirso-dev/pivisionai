"""Notification service: Webhook and MQTT."""

import json
import logging
from typing import Any, Dict, Optional
from uuid import UUID

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class NotificationService:
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
        if not settings.mqtt_enabled:
            return {"status": "skipped", "reason": "mqtt disabled"}

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

    async def notify_event(self, event: Dict[str, Any], actions: Dict[str, Any]) -> list:
        results = []
        payload = {
            "event_id": str(event.get("id", "")),
            "camera_id": str(event.get("camera_id", "")),
            "event_type": event.get("event_type"),
            "severity": event.get("severity"),
            "object_class": event.get("object_class"),
            "description": event.get("description"),
            "occurred_at": event.get("occurred_at"),
            "metadata": event.get("metadata", {}),
        }

        if actions.get("webhook") or settings.webhook_enabled:
            url = actions.get("webhook_url") or settings.webhook_default_url
            if url:
                result = await self.send_webhook(url, payload)
                results.append({"channel": "webhook", **result})

        if actions.get("mqtt") or settings.mqtt_enabled:
            topic = actions.get("mqtt_topic") or settings.mqtt_topic
            result = self.send_mqtt(topic, payload)
            results.append({"channel": "mqtt", **result})

        if actions.get("visual_alert"):
            results.append({"channel": "visual_alert", "status": "queued"})

        if actions.get("sound_alert"):
            results.append({"channel": "sound_alert", "status": "queued"})

        return results


notification_service = NotificationService()
