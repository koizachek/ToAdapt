"""Session-Datenmodell — individuell (kein Gruppen-State)."""

from datetime import datetime

from pydantic import BaseModel, Field

from backend.models.experiment import ExperimentContext


class Session(BaseModel):
    session_id: str
    user_id: str
    case_id: str
    tp_phase: int
    experiment: ExperimentContext | None = None

    # Metacognitive-First: Reflexionsphase abgeschlossen?
    metacognitive_phase_complete: bool = False

    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    message_count: int = 0


class SessionCreate(BaseModel):
    user_id: str
    case_id: str
    experiment: ExperimentContext | None = None


class SessionResponse(BaseModel):
    session_id: str
    user_id: str
    case_id: str
    tp_phase: int
    websocket_url: str
