"""WebSocket-Manager für Gruppen-Chats."""

import logging
from collections import defaultdict

from fastapi import WebSocket

import structlog

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """Verwaltet alle aktiven WebSocket-Verbindungen, gruppiert nach group_id.

    Jede Gruppe hat einen eigenen "Room". Nachrichten werden an alle
    Mitglieder des Rooms gebroadcastet.
    """

    def __init__(self) -> None:
        # group_id → {user_id: WebSocket}
        self._rooms: dict[str, dict[str, WebSocket]] = defaultdict(dict)

    async def connect(self, websocket: WebSocket, group_id: str, user_id: str) -> None:
        """Nimmt eine neue WebSocket-Verbindung an und registriert sie im Room."""
        await websocket.accept()
        self._rooms[group_id][user_id] = websocket
        logger.info("ws_connected", group_id=group_id, user_id=user_id)

    def disconnect(self, group_id: str, user_id: str) -> None:
        """Entfernt eine Verbindung aus dem Room."""
        self._rooms[group_id].pop(user_id, None)
        if not self._rooms[group_id]:
            del self._rooms[group_id]
        logger.info("ws_disconnected", group_id=group_id, user_id=user_id)

    async def broadcast(self, group_id: str, message: dict, exclude_user: str | None = None) -> None:
        """Sendet eine Nachricht an alle Mitglieder einer Gruppe."""
        room = self._rooms.get(group_id, {})
        dead: list[str] = []

        for uid, ws in room.items():
            if uid == exclude_user:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                logger.warning("ws_send_failed", group_id=group_id, user_id=uid)
                dead.append(uid)

        for uid in dead:
            self.disconnect(group_id, uid)

    async def send_to_user(self, group_id: str, user_id: str, message: dict) -> None:
        """Sendet eine Nachricht an ein einzelnes Gruppenmitglied."""
        ws = self._rooms.get(group_id, {}).get(user_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                logger.warning("ws_send_failed", group_id=group_id, user_id=user_id)
                self.disconnect(group_id, user_id)

    def online_users(self, group_id: str) -> list[str]:
        """Gibt die Liste der aktuell verbundenen User-IDs zurück."""
        return list(self._rooms.get(group_id, {}).keys())

    def is_connected(self, group_id: str, user_id: str) -> bool:
        return user_id in self._rooms.get(group_id, {})


# Singleton — wird von FastAPI als Dependency injiziert
manager = ConnectionManager()
