from typing import List, Dict, Any, Optional
from fastapi import WebSocket
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if not self.active_connections and self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

    async def broadcast(self, event_type: str, data: Dict[str, Any]):
        message = json.dumps({"type": event_type, "data": data})
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                dead_connections.append(connection)
        for conn in dead_connections:
            self.disconnect(conn)

    async def send_personal(self, websocket: WebSocket, event_type: str, data: Dict[str, Any]):
        message = json.dumps({"type": event_type, "data": data})
        try:
            await websocket.send_text(message)
        except Exception:
            self.disconnect(websocket)

    async def _heartbeat_loop(self):
        while True:
            await asyncio.sleep(30)
            await self.broadcast("heartbeat", {"timestamp": asyncio.get_event_loop().time()})


ws_manager = WebSocketManager()
