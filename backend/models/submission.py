"""Submission-Datenmodell — Studierenden-Antworten und Scoring."""

from datetime import datetime

from pydantic import BaseModel, Field


class QuestionScore(BaseModel):
    question_id: str
    bloom_level: int
    max_points: int
    awarded_points: float
    feedback: str                        # Scaffolded, kein direktes Lösung-Reveal
    learning_objective_tags: list[str]   # z.B. ["analyse", "stakeholder", "wirkungskette"]


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

    answers: dict[str, str] = Field(default_factory=dict)   # question_id → Antwort-Text
    scores: list[QuestionScore] = Field(default_factory=list)

    total_points: float = 0.0
    max_points: float = 0.0
    percentage: float = 0.0

    status: str = SubmissionStatus.IN_PROGRESS

    started_at: datetime = Field(default_factory=datetime.utcnow)
    submitted_at: datetime | None = None
    evaluated_at: datetime | None = None


class SubmissionCreate(BaseModel):
    user_id: str
    matrikelnummer: str
    case_id: str
    target_tp: int


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
    scores: list[QuestionScore]
    overall_feedback: str
