"""Presence-Tracking: wer ist in einer Gruppe gerade online."""

from backend.realtime.websocket import manager


def get_presence_message(group_id: str, display_names: dict[str, str]) -> dict:
    """Erzeugt eine Presence-Nachricht mit den aktuell Online-Mitgliedern.

    Args:
        group_id: Die Gruppen-ID.
        display_names: Mapping user_id → display_name für alle Gruppenmitglieder.

    Returns:
        Dict mit Event-Typ und Liste der Online-Namen.
    """
    online_ids = manager.online_users(group_id)
    online_names = [display_names.get(uid, uid) for uid in online_ids]
    return {
        "event": "presence_update",
        "group_id": group_id,
        "online": online_names,
        "count": len(online_names),
    }


async def broadcast_presence(group_id: str, display_names: dict[str, str]) -> None:
    """Broadcastet den aktuellen Presence-Status an alle Gruppenmitglieder."""
    msg = get_presence_message(group_id, display_names)
    await manager.broadcast(group_id, msg)
