"""Hilfsfunktionen zum Broadcasten typisierter Events an Gruppen-Rooms."""

from datetime import datetime

from backend.realtime.websocket import manager


async def broadcast_user_message(
    group_id: str,
    user_id: str,
    display_name: str,
    content: str,
    message_id: str,
) -> None:
    """Verteilt eine User-Nachricht an alle anderen Gruppenmitglieder."""
    await manager.broadcast(
        group_id,
        {
            "event": "user_message",
            "message_id": message_id,
            "group_id": group_id,
            "user_id": user_id,
            "display_name": display_name,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        },
        exclude_user=user_id,   # Sender bekommt eigene Nachricht via HTTP-Response
    )


async def broadcast_agent_response(
    group_id: str,
    agent_type: str,
    content: str,
    message_id: str,
) -> None:
    """Verteilt eine Agent-Antwort an alle Gruppenmitglieder."""
    await manager.broadcast(
        group_id,
        {
            "event": "agent_response",
            "message_id": message_id,
            "group_id": group_id,
            "agent_type": agent_type,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


async def broadcast_agent_typing(group_id: str, agent_type: str, is_typing: bool) -> None:
    """Signalisiert der Gruppe, dass ein Agent gerade antwortet."""
    await manager.broadcast(
        group_id,
        {
            "event": "agent_typing",
            "group_id": group_id,
            "agent_type": agent_type,
            "is_typing": is_typing,
        },
    )
