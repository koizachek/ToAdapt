"""LLM-Judge für Gruppenarbeiten (Running Case, TP-spezifische Kriterien).

Die Gruppen bearbeiten über die Touchpoints hinweg denselben Running Case;
bewertet wird je Touchpoint gegen die kalibrierten TP-Rubric-Dateien
(backend/config/rubrics/tp{n}_rubric.json) — dieselben Kriterien, mit denen
auch die Individualabgaben (Datei-Fallback-Pfad) bewertet werden.

Robustheits-Kette wie beim RubricEvaluator: Erst-Call → JSON-Parse
(3 Kandidaten) → Repair-Call → technical_fallback (0 Punkte,
needs_human_review=True). Bewertungs-Prompts der Individualabgaben werden
NICHT verändert, nur wiederverwendet (EVALUATOR_SYSTEM, REPAIR_PROMPT,
Parse-Helfer) — Änderungsklasse B bleibt unberührt.

Die Ergebnisse sind ausschließlich tutor-sichtbar (Dashboard/Upload-Reiter),
nie studierendensichtbar.
"""

from __future__ import annotations

import json

import structlog

from backend.config.tp_configs import TP_CONFIGS
from backend.evaluator.rubric_evaluator import (
    BLOOM_CALIBRATION_ANCHORS,
    BLOOM_TAGS,
    EVALUATOR_MAX_TOKENS,
    EVALUATOR_SYSTEM,
    LOW_BAND_FACTOR,
    MID_BAND_FACTOR,
    REPAIR_PROMPT,
    parse_evaluation_payload,
)
from backend.evaluator.rubric_loader import RUBRICS_DIR, QuestionRubric
from backend.llm import OpenRouterClient

logger = structlog.get_logger(__name__)

# Maximalpunkte pro Touchpoint — gespiegelt an den kalibrierten Fragen des
# Golden Case (q1–q4: 25/24/22/30), damit Gruppen- und Individualscores auf
# derselben Skala liegen.
GROUP_TP_MAX_POINTS: dict[int, int] = {1: 25, 2: 24, 3: 22, 4: 30}

# Bloom-Zielstufe pro TP = höchste Stufe der TP-Konfiguration.
def _tp_bloom_level(tp: int) -> int:
    levels = TP_CONFIGS.get(tp, {}).get("bloom_levels", [4])
    return max(levels)


GROUP_EVALUATE_PROMPT = """Bewerte die folgende GRUPPENARBEIT (ganzes Dokument) zu einem Running Case.

TOUCHPOINT-KONTEXT: TP{tp} — {tp_name}
Abgabeformat: {tp_format}
Leitfragen des Touchpoints:
{key_questions}

Maximale Punkte: {max_points}
Bloom-Stufe: {bloom_level}
Lernziel-Tags: {tags}
Rubric-Fokus:
{rubric_focus}

Verbindliche Canvas-Bausteine:
{canvas_blocks}

Kalibrierung:
{calibration_notes}

DOKUMENT DER GRUPPE (extrahierter Text, ggf. gekürzt):
{document}

Hinweise zur Bewertung eines Fließdokuments:
- Identifiziere selbst die Passagen, die auf den Rubric-Fokus einzahlen — die Gruppe beantwortet keine nummerierten Fragen.
- Deckblatt, Inhaltsverzeichnis und Formalia fließen nicht in die Punktzahl ein.
- Bewertet wird die Denkqualität des Gesamtdokuments gegen die Kriterien dieses Touchpoints.

Antworte mit einem JSON-Objekt:
{{
  "awarded_points": <float, 0 bis {max_points}>,
  "feedback": "<kurze Einschätzung für Tutor:innen, max 80 Wörter>",
  "learning_objective_tags": ["<tag1>", "<tag2>"],
  "canvas_alignment_score": <float, 0.0 bis 1.0>,
  "addressed_canvas_blocks": ["<block_id>"],
  "missing_canvas_blocks": ["<block_id>"],
  "canvas_rationale": "<kurze Begründung, max 50 Wörter>",
  "judge_confidence": "high|medium|low",
  "score_band": "low|partial|solid|strong",
  "main_strengths": ["<kurzer Punkt>"],
  "main_penalties": ["<kurzer Punkt>"],
  "needs_human_review": <true|false>,
  "review_reason": "<nur falls needs_human_review=true>"
}}

Vergabe-Leitlinien:
- {max_points} Punkte: Klare Entscheidungslogik, starke Argumente, durchgängiger Case-Bezug, Konsequenzen benannt
- {mid_points} Punkte: Entscheidung vorhanden, Begründung teilweise, wenig Case-Bezug
- {low_points} Punkte: Bleibt an der Oberfläche, keine Ursache-Wirkung, generisch
- 0 Punkte: Kein verwertbarer Inhalt
- Markiere needs_human_review=true bei Low Confidence, Grenzfällen oder wenn der Dokumenttext unvollständig wirkt."""


def load_tp_rubric(tp: int) -> QuestionRubric | None:
    """Lädt die (einzige) Frage-Rubric der TP-Datei als QuestionRubric."""
    path = RUBRICS_DIR / f"tp{tp}_rubric.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        questions = payload.get("questions", {})
        if not questions:
            return None
        question_id, data = next(iter(questions.items()))
        return QuestionRubric(
            rubric_reference=path.name,
            question_id=question_id,
            **{
                key: data[key]
                for key in (
                    "evaluation_focus",
                    "required_canvas_blocks",
                    "exemplar_threshold_pct",
                    "score_floor_pct",
                )
                if key in data
            },
        )
    except Exception as exc:
        logger.warning("group_tp_rubric_load_failed", tp=tp, error=str(exc))
        return None


class GroupWorkEvaluator:
    """Bewertet ein Gruppen-Dokument gegen die TP-Rubric."""

    def __init__(self, api_key: str):
        self.client = OpenRouterClient(api_key=api_key)

    def _build_prompt(self, *, tp: int, rubric: QuestionRubric | None, document: str) -> str:
        config = TP_CONFIGS.get(tp, {})
        bloom = _tp_bloom_level(tp)
        max_points = GROUP_TP_MAX_POINTS[tp]

        rubric_focus = (
            "\n".join(f"- {item}" for item in rubric.evaluation_focus)
            if rubric and rubric.evaluation_focus
            else "- Klare, fallbezogene Analyse mit nachvollziehbarer Entscheidung"
        )
        if rubric and rubric.required_canvas_blocks:
            canvas_blocks = "\n".join(
                f"- {block.block} ({block.label}): {block.expectation} "
                f"Signal-Keywords: {', '.join(block.accepted_keywords)}"
                for block in rubric.required_canvas_blocks
            )
        else:
            canvas_blocks = "- Keine spezifischen Canvas-Bausteine vorgegeben"

        anchors = BLOOM_CALIBRATION_ANCHORS.get(bloom, [])
        calibration = (
            "\n".join(f"- {note}" for note in anchors)
            if anchors
            else "- Keine spezifischen Kalibrierungsanker vorhanden."
        )

        return GROUP_EVALUATE_PROMPT.format(
            tp=tp,
            tp_name=config.get("name", f"Touchpoint {tp}"),
            tp_format=config.get("format", "PDF"),
            key_questions="\n".join(f"- {q}" for q in config.get("key_questions", [])) or "- (keine)",
            max_points=max_points,
            bloom_level=bloom,
            tags=", ".join(BLOOM_TAGS.get(bloom, ["analyse"])),
            rubric_focus=rubric_focus,
            canvas_blocks=canvas_blocks,
            calibration_notes=calibration,
            document=document,
            mid_points=round(max_points * MID_BAND_FACTOR, 1),
            low_points=round(max_points * LOW_BAND_FACTOR, 1),
        )

    def _fallback_payload(self, tags: list[str]) -> dict:
        return {
            "awarded_points": 0.0,
            "feedback": (
                "Die automatische Auswertung konnte technisch nicht abgeschlossen "
                "werden — bitte manuell bewerten."
            ),
            "learning_objective_tags": tags,
            "canvas_alignment_score": 0.0,
            "addressed_canvas_blocks": [],
            "missing_canvas_blocks": [],
            "canvas_rationale": "Technischer Fallback wegen ungueltiger Modellantwort.",
            "evaluation_status": "technical_fallback",
            "needs_human_review": True,
            "review_reason": (
                "Die Modellantwort konnte auch nach Reparaturversuch nicht als "
                "valides JSON verarbeitet werden."
            ),
            "judge_confidence": "low",
            "score_band": "unscored",
            "main_strengths": [],
            "main_penalties": ["Technischer Fallback; keine belastbare automatische Bewertung."],
        }

    async def _evaluate_with_repair(self, *, prompt: str, upload_id: str, tags: list[str]) -> dict:
        try:
            text = await self.client.complete(
                system=EVALUATOR_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=EVALUATOR_MAX_TOKENS,
            )
        except Exception as exc:
            # Transportfehler (Timeout, 429 nach SDK-Retries, …) dürfen bei
            # einem Batch-Upload nicht den ganzen Request crashen — das
            # einzelne Dokument fällt auf den technical_fallback.
            logger.error("group_evaluation_llm_failed", upload_id=upload_id, error=str(exc))
            return self._fallback_payload(tags)
        try:
            return parse_evaluation_payload(text)
        except ValueError:
            logger.warning(
                "group_evaluation_json_parse_failed",
                upload_id=upload_id,
                raw_preview=text[:500],
            )

        try:
            repaired = await self.client.complete(
                system=EVALUATOR_SYSTEM,
                messages=[
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": REPAIR_PROMPT},
                ],
                max_tokens=EVALUATOR_MAX_TOKENS,
            )
            return parse_evaluation_payload(repaired)
        except Exception:
            # ValueError (weiter kein valides JSON) ODER Transportfehler des
            # Repair-Calls — beides endet im technical_fallback.
            logger.error("group_evaluation_json_repair_failed", upload_id=upload_id)
            return self._fallback_payload(tags)

    def _score_from_payload(self, *, tp: int, data: dict, tags: list[str]) -> dict:
        """Baut den Score-Dict; wirft TypeError/ValueError bei typ-ungültigen
        Zahlen (Aufrufer fällt auf den technical_fallback zurück)."""
        max_points = GROUP_TP_MAX_POINTS[tp]
        awarded = max(0.0, min(float(data.get("awarded_points", 0.0)), float(max_points)))
        canvas = max(0.0, min(float(data.get("canvas_alignment_score", 0.0)), 1.0))

        needs_human_review = bool(data.get("needs_human_review", False))
        judge_confidence = str(data.get("judge_confidence", "") or "").lower() or None
        if judge_confidence == "low":
            needs_human_review = True
        review_reason = data.get("review_reason")

        def _strings(value: object) -> list[str]:
            if not isinstance(value, list):
                return []
            return [str(item).strip() for item in value if str(item).strip()]

        return {
            "question_id": f"tp{tp}_group_work",
            "bloom_level": _tp_bloom_level(tp),
            "max_points": max_points,
            "awarded_points": awarded,
            "feedback": str(data.get("feedback", "") or "").strip(),
            "learning_objective_tags": _strings(data.get("learning_objective_tags")) or tags,
            "rubric_reference": f"tp{tp}_rubric.json",
            "canvas_alignment_score": canvas,
            "canvas_alignment_pct": round(canvas * 100, 1),
            "addressed_canvas_blocks": _strings(data.get("addressed_canvas_blocks")),
            "missing_canvas_blocks": _strings(data.get("missing_canvas_blocks")),
            "canvas_rationale": str(data.get("canvas_rationale", "") or "").strip() or None,
            "evaluation_status": str(data.get("evaluation_status", "ok") or "ok"),
            "needs_human_review": needs_human_review,
            "review_reason": str(review_reason).strip() if review_reason else None,
            "judge_confidence": judge_confidence,
            "score_band": str(data.get("score_band", "") or "").lower() or None,
            "main_strengths": _strings(data.get("main_strengths")),
            "main_penalties": _strings(data.get("main_penalties")),
        }

    async def evaluate_document(self, *, upload_id: str, tp: int, document_text: str) -> dict:
        """Bewertet ein Dokument; Rückgabe ist ein Score-Dict (nie Exception
        aus der LLM-/Parse-Kette — schlimmstenfalls technical_fallback)."""
        if tp not in GROUP_TP_MAX_POINTS:
            raise ValueError(f"Ungültiger Touchpoint: {tp}")

        rubric = load_tp_rubric(tp)
        tags = BLOOM_TAGS.get(_tp_bloom_level(tp), ["analyse"])
        prompt = self._build_prompt(tp=tp, rubric=rubric, document=document_text)

        data = await self._evaluate_with_repair(prompt=prompt, upload_id=upload_id, tags=tags)
        try:
            return self._score_from_payload(tp=tp, data=data, tags=tags)
        except (TypeError, ValueError):
            logger.error("group_evaluation_payload_invalid_types", upload_id=upload_id)
            return self._score_from_payload(tp=tp, data=self._fallback_payload(tags), tags=tags)
