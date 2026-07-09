"""Pädagogische Qualitätsbewertung der Tutor-Antworten (LLM-as-Judge).

Framework: "Unifying AI Tutor Evaluation: An Evaluation Taxonomy for
Pedagogical Ability Assessment of LLM-Powered AI Tutors" (Maurya et al.,
NAACL 2025) — https://github.com/kaushal0494/UnifyingAITutorEvaluation
(Taxonomie/Guidelines CC BY-SA 4.0). Acht Dimensionen mit den
Original-Skalen; Auswertung als "desirability rate" pro Dimension.

Adaptionen für ToAdapt (dokumentiert, bewusst):
- MathDial/Bridge setzen voraus, dass die Studierenden-Nachricht einen
  Fehler enthält. Im Scaffolding-Chat ist das oft nicht so → die beiden
  Mistake-Dimensionen erlauben zusätzlich "Not applicable" und fließen
  dann nicht in die Desirability-Quote ein.
- "Answer" heißt hier: die Lösung/Empfehlung zur Case-Aufgabe (z.B. eine
  konkrete Priorisierung oder Entscheidung), nicht ein Mathe-Resultat.
- ToAdapt-Doktrin: "Revealing of the Answer" = JEDES Enthüllen ist
  unerwünscht (desired = "No"), unabhängig von Korrektheit.

Dieses Modul macht KEINE Live-Bewertung im Studierenden-Flow — es wird
offline von scripts/evaluate_tutor_responses.py über die geloggten
chat_turn_completed-Events betrieben (Änderungsklasse D, Forschung).
"""

from __future__ import annotations

from typing import Any

import structlog

from backend.evaluator.rubric_evaluator import parse_evaluation_payload
from backend.llm import OpenRouterClient

logger = structlog.get_logger(__name__)

TERNARY = ["Yes", "To some extent", "No"]
NA = "Not applicable"

# Reihenfolge = Reihenfolge im Paper. "desired" steuert die Aggregation.
TUTOR_EVAL_DIMENSIONS: dict[str, dict[str, Any]] = {
    "mistake_identification": {
        "name": "Mistake Identification",
        "definition": (
            "Has the tutor identified/recognized a mistake or misconception "
            "in the student's message?"
        ),
        "labels": TERNARY + [NA],
        "desired": "Yes",
        "na_allowed": True,
    },
    "mistake_location": {
        "name": "Mistake Location",
        "definition": (
            "Does the tutor's response accurately point to the location of the "
            "mistake, i.e., what exactly in the student's reasoning is off?"
        ),
        "labels": TERNARY + [NA],
        "desired": "Yes",
        "na_allowed": True,
    },
    "revealing_of_the_answer": {
        "name": "Revealing of the Answer",
        "definition": (
            "Does the tutor reveal the answer to the task — here: a concrete "
            "solution, recommendation, prioritization, or ready-made content "
            "the student is supposed to develop themselves?"
        ),
        "labels": ["Yes (and correct)", "Yes (but incorrect)", "No"],
        "desired": "No",
        "na_allowed": False,
    },
    "providing_guidance": {
        "name": "Providing Guidance",
        "definition": (
            "Does the tutor offer correct and relevant guidance, such as a "
            "hint, an explanation of a concept, a guiding question, or a "
            "pointer to relevant case material?"
        ),
        "labels": TERNARY,
        "desired": "Yes",
        "na_allowed": False,
    },
    "actionability": {
        "name": "Actionability",
        "definition": (
            "Is it clear from the tutor's response what the student should do "
            "next in their work on the case?"
        ),
        "labels": TERNARY,
        "desired": "Yes",
        "na_allowed": False,
    },
    "coherence": {
        "name": "Coherence",
        "definition": (
            "Is the tutor's response logically consistent with the student's "
            "message and the conversation so far?"
        ),
        "labels": TERNARY,
        "desired": "Yes",
        "na_allowed": False,
    },
    "tutor_tone": {
        "name": "Tutor Tone",
        "definition": "Is the tone of the tutor's response encouraging, neutral, or offensive?",
        "labels": ["Encouraging", "Neutral", "Offensive"],
        "desired": "Encouraging",
        "na_allowed": False,
    },
    "humanlikeness": {
        "name": "Humanlikeness",
        "definition": "Does the tutor's response sound natural and human-like, not robotic or templated?",
        "labels": TERNARY,
        "desired": "Yes",
        "na_allowed": False,
    },
}

JUDGE_SYSTEM = """You are an expert annotator for the pedagogical quality of AI tutor
responses, following the evaluation taxonomy of Maurya et al. (NAACL 2025,
"Unifying AI Tutor Evaluation").

Context: The tutor is a Socratic learning companion for business-case work
at a university. By design it must NOT give solutions, recommendations, or
framework names — it scaffolds the student's own thinking. The dialogue may
be in German or English; annotate regardless of language.

For EACH of the eight dimensions, choose EXACTLY one of the allowed labels
(copy the label string verbatim) and give a one-sentence justification.

If the student's message contains no identifiable mistake or misconception,
label mistake_identification and mistake_location as "Not applicable".

You respond ONLY with a valid JSON object. No text before or after it."""

JUDGE_PROMPT = """DIALOGUE CONTEXT (may be empty):
{context}

STUDENT'S MESSAGE:
{student_message}

TUTOR'S RESPONSE (to annotate):
{tutor_response}

Dimensions and allowed labels:
{dimension_spec}

Respond with a JSON object of this exact shape:
{{
{json_spec}
}}"""


def _dimension_spec() -> str:
    lines = []
    for key, dim in TUTOR_EVAL_DIMENSIONS.items():
        labels = " | ".join(f'"{label}"' for label in dim["labels"])
        lines.append(f"- {key} ({dim['name']}): {dim['definition']} Labels: {labels}")
    return "\n".join(lines)


def _json_spec() -> str:
    return ",\n".join(
        f'  "{key}": {{"label": "<one allowed label>", "justification": "<one sentence>"}}'
        for key in TUTOR_EVAL_DIMENSIONS
    )


def build_judge_prompt(*, context: str, student_message: str, tutor_response: str) -> str:
    return JUDGE_PROMPT.format(
        context=context.strip() or "(none)",
        student_message=student_message.strip(),
        tutor_response=tutor_response.strip(),
        dimension_spec=_dimension_spec(),
        json_spec=_json_spec(),
    )


def normalize_annotation(data: dict) -> dict[str, dict[str, str]]:
    """Validiert Judge-Output gegen die erlaubten Labels.

    Ungültige/fehlende Labels werden als "Invalid" markiert (fließen nicht
    in die Desirability ein, tauchen aber in der Auswertung auf).
    """
    result: dict[str, dict[str, str]] = {}
    for key, dim in TUTOR_EVAL_DIMENSIONS.items():
        raw = data.get(key)
        label = ""
        justification = ""
        if isinstance(raw, dict):
            label = str(raw.get("label", "")).strip()
            justification = str(raw.get("justification", "")).strip()
        elif isinstance(raw, str):
            label = raw.strip()

        matched = next(
            (allowed for allowed in dim["labels"] if allowed.lower() == label.lower()),
            None,
        )
        result[key] = {
            "label": matched if matched else "Invalid",
            "justification": justification,
        }
    return result


class TutorResponseEvaluator:
    """LLM-as-Judge über einzelne Tutor-Turns (offline/Forschung)."""

    def __init__(self, api_key: str, model: str | None = None):
        self.client = OpenRouterClient(api_key=api_key, model=model)

    async def evaluate_turn(
        self,
        *,
        context: str,
        student_message: str,
        tutor_response: str,
    ) -> dict[str, dict[str, str]]:
        prompt = build_judge_prompt(
            context=context,
            student_message=student_message,
            tutor_response=tutor_response,
        )
        text = await self.client.complete(
            system=JUDGE_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
        )
        try:
            data = parse_evaluation_payload(text)
        except ValueError:
            logger.warning("tutor_eval_json_parse_failed", raw_preview=text[:300])
            data = {}
        return normalize_annotation(data)


def aggregate_annotations(rows: list[dict]) -> dict:
    """Aggregiert Annotationen zu Label-Verteilungen und Desirability-Quoten.

    rows: [{"agent_type": str, "annotation": {dim: {"label": ...}}}, ...]
    Desirability pro Dimension = Anteil desired-Label an allen GÜLTIGEN
    Labels (ohne "Not applicable" und "Invalid").
    """
    def empty_bucket() -> dict:
        return {
            key: {"counts": {}, "valid": 0, "desired": 0}
            for key in TUTOR_EVAL_DIMENSIONS
        }

    overall = empty_bucket()
    by_agent: dict[str, dict] = {}

    for row in rows:
        agent = str(row.get("agent_type") or "unknown")
        buckets = [overall, by_agent.setdefault(agent, empty_bucket())]
        annotation = row.get("annotation", {})
        for key, dim in TUTOR_EVAL_DIMENSIONS.items():
            label = (annotation.get(key) or {}).get("label", "Invalid")
            for bucket in buckets:
                slot = bucket[key]
                slot["counts"][label] = slot["counts"].get(label, 0) + 1
                if label not in (NA, "Invalid"):
                    slot["valid"] += 1
                    if label == dim["desired"]:
                        slot["desired"] += 1

    def finalize(bucket: dict) -> dict:
        out = {}
        for key, slot in bucket.items():
            out[key] = {
                "counts": slot["counts"],
                "n_valid": slot["valid"],
                "desirability_rate": (
                    round(slot["desired"] / slot["valid"], 3) if slot["valid"] else None
                ),
                "desired_label": TUTOR_EVAL_DIMENSIONS[key]["desired"],
            }
        return out

    return {
        "n_items": len(rows),
        "overall": finalize(overall),
        "by_agent_type": {agent: finalize(bucket) for agent, bucket in by_agent.items()},
    }
