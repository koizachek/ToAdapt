"""Session-Datenmodell."""

from datetime import datetime

from pydantic import BaseModel, Field


class Session(BaseModel):
    """Eine einzelne Chat-Session einer Gruppe (flüchtiger Zustand)."""

    session_id: str
    group_id: str
    tp_phase: int

    # Metacognitive-First: wurde die Reflexionsphase abgeschlossen?
    metacognitive_phase_complete: bool = False

    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    message_count: int = 0


class SessionCreate(BaseModel):
    """Request-Schema zum Erstellen einer neuen Session."""

    group_id: str
    user_id: str


class SessionResponse(BaseModel):
    """Response-Schema nach Session-Erstellung."""

    session_id: str
    group_id: str
    tp_phase: int
    websocket_url: str
