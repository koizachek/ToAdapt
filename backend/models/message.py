"""Nachrichten-Datenmodell."""

from datetime import datetime
from backend.timeutils import naive_utcnow
from pydantic import BaseModel, Field


class AgentType:
    METACOGNITIVE = "metacognitive"
    STRATEGIC = "strategic"
    CONCEPTUAL = "conceptual"
    PROCEDURAL = "procedural"


class Message(BaseModel):
    message_id: str
    session_id: str
    user_id: str
    role: str                        # "user" | "agent"
    content: str
    agent_type: str | None = None
    guardrails_triggered: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=naive_utcnow)
