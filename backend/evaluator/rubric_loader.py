"""Lädt fragebezogene Rubrics inkl. Business-Model-Canvas-Signalen."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from backend.models.case import CaseQuestion

RUBRICS_DIR = Path(__file__).resolve().parent.parent / "config" / "rubrics"


class CanvasBlockCriterion(BaseModel):
    block: str
    label: str
    accepted_keywords: list[str] = Field(default_factory=list)
    expectation: str
    weight: float = 1.0


class QuestionRubric(BaseModel):
    rubric_reference: str
    question_id: str
    evaluation_focus: list[str] = Field(default_factory=list)
    required_canvas_blocks: list[CanvasBlockCriterion] = Field(default_factory=list)
    exemplar_threshold_pct: float = 80.0
    score_floor_pct: float = 75.0


def load_question_rubric(question: CaseQuestion) -> QuestionRubric | None:
    rubric_path = RUBRICS_DIR / question.rubric_reference
    if not rubric_path.exists():
        return None

    payload = json.loads(rubric_path.read_text(encoding="utf-8"))
    question_data = payload.get("questions", {}).get(question.question_id)
    if not question_data:
        question_data = payload.get("default")
    if not question_data:
        return None

    return QuestionRubric.model_validate({
        "rubric_reference": question.rubric_reference,
        "question_id": question.question_id,
        **question_data,
    })
