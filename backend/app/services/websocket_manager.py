"""WebSocket connection manager for real-time events."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info("WebSocket connected. Total: %d", len(self.active_connections))

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info("WebSocket disconnected. Total: %d", len(self.active_connections))

    async def broadcast(self, message: Dict[str, Any]):
        if not self.active_connections:
            return

        data = json.dumps(message, default=str)
        disconnected = []

        async with self._lock:
            connections = list(self.active_connections)

        for connection in connections:
            try:
                await connection.send_text(data)
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            await self.disconnect(conn)

    async def send_event(self, event: Dict[str, Any]):
        await self.broadcast({"type": "event", "data": event})

    async def send_health(self, health: Dict[str, Any]):
        await self.broadcast({"type": "health", "data": health})

    async def send_alert(self, alert: Dict[str, Any]):
        await self.broadcast({"type": "alert", "data": alert})


ws_manager = ConnectionManager()
