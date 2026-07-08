"""Lädt fragebezogene Rubrics inkl. Business-Model-Canvas-Signalen.

Zwei Quellen, feste Vorrangregel:
1. EINGEBETTETES CASE-PAKET (question.evaluation_focus / required_canvas_blocks)
   — neue, generierte Cases tragen ihre Rubric selbst; nur so überleben sie
   Redeploys (Mongo) und erben nicht fremde Bewertungskriterien.
2. DATEI-FALLBACK (backend/config/rubrics/tp{n}_rubric.json) — kalibriert auf
   den kuratierten Alpes-Bank-Case; bleibt für Alt-Cases ohne eingebettetes
   Paket bestehen. Dateien sind zur Laufzeit statisch und werden gecacht.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

from backend.models.case import CaseQuestion

RUBRICS_DIR = Path(__file__).resolve().parent.parent / "config" / "rubrics"

DEFAULT_EXEMPLAR_THRESHOLD_PCT = 80.0
DEFAULT_SCORE_FLOOR_PCT = 75.0


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
    exemplar_threshold_pct: float = DEFAULT_EXEMPLAR_THRESHOLD_PCT
    score_floor_pct: float = DEFAULT_SCORE_FLOOR_PCT


def _embedded_rubric(question: CaseQuestion) -> QuestionRubric:
    return QuestionRubric(
        rubric_reference=question.rubric_reference or "embedded",
        question_id=question.question_id,
        evaluation_focus=list(question.evaluation_focus),
        required_canvas_blocks=[
            CanvasBlockCriterion.model_validate(block.model_dump())
            for block in question.required_canvas_blocks
        ],
        exemplar_threshold_pct=(
            question.exemplar_threshold_pct
            if question.exemplar_threshold_pct is not None
            else DEFAULT_EXEMPLAR_THRESHOLD_PCT
        ),
        score_floor_pct=(
            question.score_floor_pct
            if question.score_floor_pct is not None
            else DEFAULT_SCORE_FLOOR_PCT
        ),
    )


@lru_cache(maxsize=32)
def _load_rubric_payload(path_str: str) -> str | None:
    """Liest eine Rubric-Datei einmalig (Cache) — Rückgabe als JSON-String,
    damit der Cache-Inhalt unveränderlich bleibt."""
    path = Path(path_str)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def load_question_rubric(question: CaseQuestion) -> QuestionRubric | None:
    """Liefert die Rubric der Frage (eingebettet vor Datei) oder None."""
    if question.evaluation_focus or question.required_canvas_blocks:
        return _embedded_rubric(question)

    if not question.rubric_reference:
        return None

    raw = _load_rubric_payload(str(RUBRICS_DIR / question.rubric_reference))
    if raw is None:
        return None

    payload = json.loads(raw)
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
