"""Submission-Datenmodell — Studierenden-Antworten und Scoring."""

from datetime import datetime

from pydantic import BaseModel, Field

from backend.models.experiment import ExperimentContext


class QuestionScore(BaseModel):
    question_id: str
    bloom_level: int
    max_points: int
    awarded_points: float
    feedback: str                        # Scaffolded, kein direktes Lösung-Reveal
    learning_objective_tags: list[str]   # z.B. ["analyse", "stakeholder", "wirkungskette"]
    rubric_reference: str | None = None
    canvas_alignment_score: float = 0.0
    canvas_alignment_pct: float = 0.0
    required_canvas_blocks: list[str] = Field(default_factory=list)
    addressed_canvas_blocks: list[str] = Field(default_factory=list)
    missing_canvas_blocks: list[str] = Field(default_factory=list)
    canvas_rationale: str | None = None
    evaluation_status: str = "ok"
    needs_human_review: bool = False
    review_reason: str | None = None
    judge_confidence: str | None = None
    score_band: str | None = None
    main_strengths: list[str] = Field(default_factory=list)
    main_penalties: list[str] = Field(default_factory=list)


class SubmissionStatus(str):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    EVALUATED = "evaluated"


class Submission(BaseModel):
    submission_id: str
    user_id: str
    matrikelnummer: str                  # Denormalisiert für Dashboard-Queries
    case_id: str
    target_tp: int
    experiment: ExperimentContext | None = None

    answers: dict[str, str] = Field(default_factory=dict)   # question_id → Antwort-Text
    scores: list[QuestionScore] = Field(default_factory=list)

    total_points: float = 0.0
    max_points: float = 0.0
    percentage: float = 0.0
    canvas_alignment_pct: float = 0.0
    rubric_fit_pct: float = 0.0
    canvas_exemplar_candidate: bool = False

    status: str = SubmissionStatus.IN_PROGRESS

    started_at: datetime = Field(default_factory=datetime.utcnow)
    submitted_at: datetime | None = None
    evaluated_at: datetime | None = None


class SubmissionCreate(BaseModel):
    user_id: str
    matrikelnummer: str | None = None
    case_id: str
    target_tp: int
    experiment: ExperimentContext | None = None


class AnswerSubmit(BaseModel):
    question_id: str
    answer_text: str


class SubmissionResult(BaseModel):
    """Rückgabe nach Evaluation — keine Rohdaten, nur Scores + Feedback."""
    submission_id: str
    case_id: str
    total_points: float
    max_points: float
    percentage: float
    canvas_alignment_pct: float = 0.0
    rubric_fit_pct: float = 0.0
    canvas_exemplar_candidate: bool = False
    canvas_summary: str | None = None
    scores: list[QuestionScore]
    overall_feedback: str
