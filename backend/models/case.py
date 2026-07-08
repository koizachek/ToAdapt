"""Case-Datenmodell — Mini-Cases für den Transfer-Trainer."""

from datetime import datetime
from backend.timeutils import naive_utcnow


from pydantic import BaseModel, Field


class CaseStatus(str):
    DRAFT = "draft"          # AI-generiert, noch nicht reviewed
    APPROVED = "approved"    # Vom Dozenten freigegeben
    REJECTED = "rejected"    # Abgelehnt, nicht im Pool
    RETIRED = "retired"      # War approved, aus dem Pool genommen


class CaseDifficulty(str):
    TP1 = "tp1"    # Verstehen & Analysieren
    TP2 = "tp2"    # Entscheiden & Priorisieren
    TP3 = "tp3"    # Operationalisieren
    TP4 = "tp4"    # Integrieren & Reflektieren
    FULL = "full"  # Alle Phasen (Klausur-Simulation)


class CaseExhibit(BaseModel):
    exhibit_id: str
    title: str
    content: str            # Freitext oder Markdown-Tabelle
    exhibit_type: str       # "table" | "text" | "quote"


class CaseSection(BaseModel):
    section_id: str
    title: str
    content: str


class CaseQuestion(BaseModel):
    question_id: str
    phase: int              # 1–4, entspricht TP/Bloom-Stufe
    bloom_level: int        # 2–6
    text: str
    max_points: int
    rubric_reference: str   # z.B. "tp2_rubric.json"
    allowed_frameworks: list[str] = Field(default_factory=list)
    forbidden_framework_names: list[str] = Field(default_factory=list)


class CaseEditEvent(BaseModel):
    """Ein Eintrag der Bearbeitungs-Historie (Editor-/Regenerier-Aktionen)."""
    at: datetime = Field(default_factory=naive_utcnow)
    editor: str = ""
    action: str = ""            # "edited" | "regenerated" | "approved" | ...
    detail: str = ""


class Case(BaseModel):
    case_id: str
    title: str
    industry: str           # z.B. "Mobility", "Retail", "HealthTech"
    country: str            # Herkunft des fiktiven Unternehmens
    tagline: str            # Ein-Satz-Beschreibung
    difficulty: str         # CaseDifficulty
    target_tp: int          # 1–4 oder 0 für FULL
    language: str = "de"    # "de" | "en"
    translated_from: str | None = None

    sections: list[CaseSection] = Field(default_factory=list)
    exhibits: list[CaseExhibit] = Field(default_factory=list)
    questions: list[CaseQuestion] = Field(default_factory=list)

    status: str = CaseStatus.DRAFT
    generated_by: str = "ai"       # "ai" | "manual"
    reviewed_by: str | None = None
    review_notes: str = ""

    revision: int = 1
    edit_history: list[CaseEditEvent] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=naive_utcnow)
    updated_at: datetime | None = None
    approved_at: datetime | None = None


class CaseSummary(BaseModel):
    """Kompakte Darstellung für Pool-Übersicht und Dashboard."""
    case_id: str
    title: str
    industry: str
    difficulty: str
    status: str
    created_at: datetime
    language: str = "de"
    translated_from: str | None = None
