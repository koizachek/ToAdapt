"""Session-Datenmodell — individuell (kein Gruppen-State)."""

from datetime import datetime

from pydantic import BaseModel, Field


class Session(BaseModel):
    session_id: str
    user_id: str
    case_id: str
    tp_phase: int

    # Metacognitive-First: Reflexionsphase abgeschlossen?
    metacognitive_phase_complete: bool = False

    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    message_count: int = 0


class SessionCreate(BaseModel):
    user_id: str
    case_id: str


class SessionResponse(BaseModel):
    session_id: str
    user_id: str
    case_id: str
    tp_phase: int
    websocket_url: str
