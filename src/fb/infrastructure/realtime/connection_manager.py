from __future__ import annotations

from fastapi import WebSocket


class ConnectionManager:
    """Manages active WebSocket connections per user.

    Supports multiple connections per user (e.g. multiple tabs/devices).
    Dead connections are automatically pruned during send operations.
    """

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        """Accept the WebSocket handshake and register the connection."""
        await websocket.accept()
        if user_id not in self._connections:
            self._connections[user_id] = set()
        self._connections[user_id].add(websocket)

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        """Remove a connection. Clean up the user entry when empty."""
        if user_id in self._connections:
            self._connections[user_id].discard(websocket)
            if not self._connections[user_id]:
                del self._connections[user_id]

    async def send_to_user(self, user_id: str, message: dict) -> None:
        """Send *message* to every connection belonging to *user_id*.

        Connections that raise on ``send_json`` are considered dead and
        removed silently.
        """
        if user_id not in self._connections:
            return

        dead: list[WebSocket] = []
        for ws in self._connections[user_id]:
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 – any transport error means dead
                dead.append(ws)

        for ws in dead:
            self._connections[user_id].discard(ws)
        if user_id in self._connections and not self._connections[user_id]:
            del self._connections[user_id]

    async def broadcast(self, user_ids: list[str], message: dict) -> None:
        """Send *message* to all connections of every user in *user_ids*."""
        for uid in user_ids:
            await self.send_to_user(uid, message)

    def get_online_users(self) -> set[str]:
        """Return the set of currently connected user IDs."""
        return set(self._connections.keys())

    def is_online(self, user_id: str) -> bool:
        """Return ``True`` if *user_id* has at least one active connection."""
        return user_id in self._connections and len(self._connections[user_id]) > 0
