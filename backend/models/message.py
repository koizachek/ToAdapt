"""Nachrichten-Datenmodell."""

from datetime import datetime

from pydantic import BaseModel, Field


class MessageRole(str):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class AgentType(str):
    METACOGNITIVE = "metacognitive"
    STRATEGIC = "strategic"
    CONCEPTUAL = "conceptual"
    PROCEDURAL = "procedural"


class Message(BaseModel):
    """Eine einzelne Nachricht in einer Gruppenkonversation."""

    message_id: str
    session_id: str
    group_id: str

    role: str                               # MessageRole
    content: str

    # Nur bei Agent-Nachrichten
    agent_type: str | None = None           # AgentType
    guardrails_triggered: list[str] = Field(default_factory=list)

    # Nur bei User-Nachrichten
    user_id: str | None = None
    display_name: str | None = None

    timestamp: datetime = Field(default_factory=datetime.utcnow)
