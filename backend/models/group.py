"""Gruppen-Datenmodell."""

from datetime import datetime
from enum import IntEnum

from pydantic import BaseModel, Field


class TPPhase(IntEnum):
    TP1 = 1
    TP2 = 2
    TP3 = 3
    TP4 = 4


class ScaffoldingIntensity(str):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class GroupMember(BaseModel):
    user_id: str
    display_name: str
    joined_at: datetime = Field(default_factory=datetime.utcnow)


class GroupMemoryState(BaseModel):
    """Persistenter Lernzustand der Gruppe über alle TPs."""

    # TP1-Ergebnisse
    tp1_challenges: list[str] = Field(default_factory=list)
    tp1_stakeholders: list[str] = Field(default_factory=list)

    # TP2-Ergebnisse
    tp2_strategy: str = ""
    tp2_tradeoffs: list[str] = Field(default_factory=list)
    tp2_kpi: str = ""

    # TP3-Ergebnisse
    tp3_decisions: dict[str, str] = Field(default_factory=dict)
    tp3_consistency_assessment: str = ""


class Group(BaseModel):
    """Eine Studierendengruppe (6 Personen) über das gesamte Semester."""

    group_id: str
    group_code: str                          # Login-Code für die Gruppe
    exercise_group: str                      # Übungsgruppe (ÜGL), z.B. "ÜGL-12"
    members: list[GroupMember] = Field(default_factory=list)
    language: str = "de"                     # "de" | "en"

    current_tp: TPPhase = TPPhase.TP1
    scaffolding_intensity: str = "medium"
    metacognitive_readiness: float = 0.0    # 0.0–1.0

    memory: GroupMemoryState = Field(default_factory=GroupMemoryState)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
