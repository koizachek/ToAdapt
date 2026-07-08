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


class GlossaryTermSpec(BaseModel):
    """Glossar-Begriff des Cases — Begriffe müssen wörtlich im Case-Text
    vorkommen, damit das Frontend sie hervorheben kann."""
    term: str
    explanation: str = ""
    starter_prompt: str = ""    # startet den Lernchat zu diesem Begriff


class AgentGuidance(BaseModel):
    """Case-spezifischer Kontext für die Scaffolding-Agenten."""
    case_summary: str = ""
    key_tensions: list[str] = Field(default_factory=list)
    common_mistakes: list[str] = Field(default_factory=list)


class CanvasBlockSpec(BaseModel):
    """Case-eigene Canvas-Vorgabe pro Frage (Teil des Case-Pakets)."""
    block: str              # z.B. "value_propositions"
    label: str              # Anzeigename, z.B. "Value Propositions"
    accepted_keywords: list[str] = Field(default_factory=list)
    expectation: str = ""   # Was die Antwort zeigen muss
    weight: float = 1.0


class CaseQuestion(BaseModel):
    question_id: str
    phase: int              # 1–4, entspricht TP/Bloom-Stufe
    bloom_level: int        # 2–6
    text: str
    max_points: int
    rubric_reference: str   # z.B. "tp2_rubric.json" — Datei-FALLBACK für Alt-Cases
    allowed_frameworks: list[str] = Field(default_factory=list)
    forbidden_framework_names: list[str] = Field(default_factory=list)

    # Eingebettetes Case-Paket (hat Vorrang vor der rubric_reference-Datei):
    # Bewertungsfokus + Canvas-Signale werden mit dem Case generiert und von
    # der Lehrperson im Editor kuratiert. calibration_notes sind die case-
    # spezifischen Bewertungs-Anker (ersetzen die generischen Bloom-Anker).
    evaluation_focus: list[str] = Field(default_factory=list)
    required_canvas_blocks: list[CanvasBlockSpec] = Field(default_factory=list)
    calibration_notes: list[str] = Field(default_factory=list)
    exemplar_threshold_pct: float | None = None
    score_floor_pct: float | None = None

    # Wortlimits pro Frage (None → Frontend-Fallback nach Frage-Index,
    # erhält das Verhalten des Alpes-Bank-Cases).
    min_words: int | None = None
    max_words: int | None = None


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

    # Case-Paket: Glossar (Lernchat-Chips) und Agenten-Kontext. Der Alpes-
    # Bank-Case nutzt historisch Frontend-Hardcodes bzw. die -agent.json-
    # Pool-Datei als Fallback — neue Cases bringen beides hier mit.
    glossary: list[GlossaryTermSpec] = Field(default_factory=list)
    agent_guidance: AgentGuidance | None = None

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
