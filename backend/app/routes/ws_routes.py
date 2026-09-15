import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from app.auth import decode_access_token
from app.websocket_manager import manager

logger = logging.getLogger("ws_routes")
router = APIRouter(tags=["WebSockets"])

@router.websocket("/ws/updates")
async def websocket_updates_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """
    Real-time WebSocket updates endpoint.
    Requires authentication via ?token=<JWT>.
    Associates the connection with the authenticated user ID for strict data isolation.
    """
    if not token:
        logger.warning("WebSocket connection attempt missing authentication token.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = decode_access_token(token)
        user_id_str = payload.get("sub")
        if not user_id_str:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        user_id = int(user_id_str)
    except Exception as e:
        logger.warning(f"WebSocket token validation failed: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Accept and register connection with connection manager
    await manager.connect(websocket, user_id)

    try:
        # Keep connection alive, listen for incoming messages (e.g. ping/pong)
        while True:
            data = await websocket.receive_text()
            # Optionally handle client messages if needed
            if data == "ping":
                await websocket.send_text('{"event": "pong"}')
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.warning(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(websocket, user_id)
