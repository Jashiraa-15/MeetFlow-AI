import json
import logging
from datetime import datetime, date, timezone
from typing import Dict, Set, Any, Optional
from fastapi import WebSocket

logger = logging.getLogger("websocket_manager")

class DateTimeJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

class ConnectionManager:
    def __init__(self):
        # Maps user_id -> Set of active WebSockets
        self.active_connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        """Accepts WebSocket connection and registers it under user_id."""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        logger.info(f"WebSocket client connected for user {user_id}. Total connections for user: {len(self.active_connections[user_id])}")

    def disconnect(self, websocket: WebSocket, user_id: int):
        """Removes disconnected WebSocket cleanly."""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"WebSocket client disconnected for user {user_id}.")

    async def broadcast_to_user(self, user_id: int, message: Dict[str, Any]):
        """
        Broadcasts a JSON message to all active WebSocket connections belonging to user_id.
        Handles failed/broken connections cleanly without crashing.
        """
        if user_id not in self.active_connections:
            return

        # Ensure timestamp is attached
        if "timestamp" not in message:
            message["timestamp"] = datetime.now(timezone.utc).isoformat()

        json_payload = json.dumps(message, cls=DateTimeJSONEncoder)
        dead_connections = set()

        for connection in list(self.active_connections[user_id]):
            try:
                await connection.send_text(json_payload)
            except Exception as e:
                logger.warning(f"Failed to send WS message to user {user_id}, marking connection dead: {e}")
                dead_connections.add(connection)

        # Cleanup dead connections
        for dead in dead_connections:
            self.disconnect(dead, user_id)

    async def broadcast_to_users(self, user_ids: list[int], message: Dict[str, Any]):
        """Broadcasts message to multiple user IDs."""
        for uid in set(user_ids):
            await self.broadcast_to_user(uid, message)

manager = ConnectionManager()
