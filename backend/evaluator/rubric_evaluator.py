"""Rubric-Evaluator — bewertet Studierenden-Antworten gegen Bloom-Lernziele.

Prinzipien:
- Pfadoffenheit: mehrere valide Antwortpfade können volle Punkte erreichen
- Kein Answer-Reveal: Feedback scaffolded, nicht lösungsgebend
- Konservativ: Unsicherheit → needs_human_review, nie stilles Raten

Aufbau der Datei:
1. Konstanten (Schwellen, Prompts, Bloom-Anker, Verbotslisten)
2. Reine Modul-Helfer (JSON-Extraktion — ohne LLM, direkt testbar)
3. RubricEvaluator: Prompt-Bau → LLM-Call mit Repair → Score-Bau → Aggregate

Robustheits-Kette pro Frage: Erst-Call → JSON-Parse (3 Kandidaten) →
Repair-Call → technical_fallback (0 Punkte, needs_human_review=True).
Auch typ-ungültige Zahlen im Judge-JSON landen im technical_fallback
statt als 500 beim Studierenden.
"""

import asyncio
import json
import re

import structlog

from backend.evaluator.rubric_loader import QuestionRubric, load_question_rubric
from backend.llm import OpenRouterClient
from backend.models.case import Case, CaseQuestion
from backend.models.submission import QuestionScore, Submission, SubmissionResult

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Konstanten — Werte sind durch die Teacher-Alignment-Studie (2026-05-31)
# kalibriert; Änderungen sind Änderungsklasse B (Alignment-Recheck!).
# ---------------------------------------------------------------------------

EVALUATOR_MAX_TOKENS = 1200

# Punktband-Anker im Prompt: mid/low relativ zur Maximalpunktzahl.
MID_BAND_FACTOR = 0.55
LOW_BAND_FACTOR = 0.25

# rubric_fit = Score und Canvas-Anwendung, 70/30 gewichtet.
RUBRIC_FIT_SCORE_WEIGHT = 0.7
RUBRIC_FIT_CANVAS_WEIGHT = 0.3

# Exemplar-Defaults, falls keine Rubric Schwellen liefert (min() über Rubrics).
FALLBACK_EXEMPLAR_CANVAS_PCT = 80.0
FALLBACK_EXEMPLAR_SCORE_PCT = 75.0

# Gesamtfeedback-Bänder (Prozent).
OVERALL_STRONG_PCT = 80
OVERALL_SOLID_PCT = 60
OVERALL_SURFACE_PCT = 40

# Canvas-Summary-Bänder (Prozent).
CANVAS_BROAD_PCT = 70
CANVAS_PARTIAL_PCT = 40

# Lernziel-Tags pro Bloom-Stufe (Fallback: "analyse").
BLOOM_TAGS: dict[int, list[str]] = {
    2: ["verstehen", "identifizieren"],
    3: ["anwenden", "transfer"],
    4: ["analysieren", "wirkungskette", "stakeholder"],
    5: ["evaluieren", "trade-off", "kpi"],
    6: ["synthese", "integration", "reflexion"],
}

DISALLOWED_FEEDBACK_PATTERNS = [
    "du solltest schreiben",
    "erste herausforderung könnte sein",
    "hier ist eine mögliche antwort",
    "die richtige antwort ist",
    "tamara sollte",
    "wähle den",
    "waehle den",
    "finma",
    "swiss hosting",
    "azure switzerland",
    "vendor lock-in",
    "vendor lock in",
    "microsoft",
]

EVALUATOR_SYSTEM = """Du bist ein Bewertungsassistent für BWL.

Du bewertest Studierenden-Antworten auf Basis von pfadoffenen Rubrics.

BEWERTUNGSPRINZIPIEN:
- Es gibt keine einzig richtige Antwort. Jede schlüssig begründete Entscheidung kann volle Punktzahl erreichen.
- Bewertet wird die Qualität des Denkens, nicht die sprachliche Glätte.
- Framework-Namen müssen NICHT genannt werden — die Logik muss angewendet werden.
- Generische Aussagen ohne konkreten Case-Bezug erhalten keine Spitzenpunkte.
- Dein Feedback ist scaffolded: Du zeigst Denkrichtungen auf, gibst aber keine Musterlösung.
- Nutze nur Informationen, die im Case oder in der Antwort des Studierenden explizit vorkommen.
- Keine erfundenen Zusatzdetails wie Regulatoren, Hosting-Setups, Vertragsklauseln oder Anbieter-Implementierungsdetails.

FEEDBACK-FORMAT (pro Frage):
- Was gut funktioniert (1–2 Sätze)
- Was fehlt oder schwach ist (1–2 Sätze, als Frage formuliert)
- Keine direkte Antwort nennen
- Keine Satzbausteine zum Abschreiben wie "du solltest schreiben..."
- Ton: klar, ruhig, nicht slangig, keine Emojis

Wenn eine Canvas-Rubric vorliegt, prüfst du explizit, ob die relevanten Business-Model-Canvas-Bausteine inhaltlich angewendet wurden.
Keywords sind nur Signale. Entscheidend ist die Qualität der Anwendung auf den Fall.

Du unterstützt Lehrende bei der Bewertung. Vergib Punkte konservativ entlang der Rubric,
markiere unsichere oder technisch problematische Fälle zur menschlichen Prüfung und
behaupte keine Genauigkeit, wenn die Antwort zwischen zwei Bewertungsbändern liegt.

Du antwortest AUSSCHLIESSLICH mit einem validen JSON-Objekt. Kein Text davor oder danach."""


EVALUATE_PROMPT = """Bewerte die folgende Studierenden-Antwort auf die Prüfungsfrage.

CASE-KONTEXT: {case_title} ({case_industry})

FRAGE: {question_text}
Maximale Punkte: {max_points}
Bloom-Stufe: {bloom_level}
Lernziel-Tags: {tags}
Rubric-Fokus:
{rubric_focus}

Verbindliche Canvas-Bausteine:
{canvas_blocks}

Kalibrierung aus Lehrerbewertungen:
{calibration_notes}

ANTWORT DES STUDIERENDEN:
{answer}

Antworte mit einem JSON-Objekt:
{{
  "awarded_points": <float, 0 bis {max_points}>,
  "feedback": "<scaffolded feedback, max 80 Wörter>",
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
- {max_points} Punkte: Klare Entscheidung, 2 starke Argumente, Case-Bezug, Konsequenzen benannt
- {mid_points} Punkte: Entscheidung vorhanden, Begründung teilweise, wenig Case-Bezug
- {low_points} Punkte: Analyse bleibt an der Oberfläche, keine Ursache-Wirkung, generisch
- 0 Punkte: Keine verwertbare Antwort
- Wenn ein Pflichtbestandteil der Frage fehlt, darf die Antwort trotz guter Teilaspekte nicht in das obere Bewertungsband.
- Fehlende Canvas-Logik ist ein substanzieller Abzug, wenn Canvas-Bausteine verbindlich vorgegeben sind.
- Markiere needs_human_review=true bei Low Confidence, Grenzfällen, widersprüchlichen Antworten oder technischen Unsicherheiten.

Canvas-Scoring:
- 1.0: Die relevanten Canvas-Bausteine werden korrekt, fallbezogen und integriert angewendet.
- 0.5: Einige passende Bausteine werden angesprochen, aber nur teilweise oder oberflächlich.
- 0.0: Keine belastbare Canvas-Logik erkennbar."""

REPAIR_PROMPT = """Deine letzte Antwort war kein valides JSON.

Gib jetzt ausschliesslich ein valides JSON-Objekt zurueck, ohne Markdown, ohne Code-Fences, ohne Erklaerungen."""

# Generische Kalibrierungsanker pro Bloom-Stufe — greifen NUR, wenn der Case
# keine eigenen calibration_notes mitbringt (neu generierte Cases vor der
# Nachkalibrierung). Case-agnostisch formuliert; die case-spezifischen Anker
# des Alpes-Bank-Cases liegen in dessen Case-JSON.
BLOOM_CALIBRATION_ANCHORS: dict[int, list[str]] = {
    2: [
        "Verständnis zeigt sich in eigenen Worten mit konkretem Fallbezug; reine Definitionswiedergabe begrenzt den Score.",
        "Zentrale Fallmerkmale müssen korrekt wiedergegeben werden, nicht nur allgemeines Branchenwissen.",
    ],
    3: [
        "Anwendung verlangt die Übertragung auf konkrete Fallmerkmale; generische Aussagen ohne Fallbezug begrenzen den Score deutlich.",
        "Die Antwort muss zeigen, WIE ein Vorgehen im Fall funktioniert, nicht nur DASS es sinnvoll wäre.",
    ],
    4: [
        "Analyse verlangt Zerlegung in Teilaspekte UND deren Wechselwirkung (z.B. externer Druck vs. interne Gegebenheiten).",
        "Reine Aufzählungen ohne Begründungslogik oder Wirkungskette begrenzen den Score deutlich.",
        "Verfehlt die Antwort die strategische Kernfrage zugunsten reiner Umsetzungsdetails, wird das streng bewertet.",
    ],
    5: [
        "Evaluation verlangt eine eindeutige Priorisierung oder Entscheidung mit nachvollziehbaren Kriterien; Optionen nur zu beschreiben reicht nicht.",
        "Ein Zielkonflikt muss aus der eigenen Empfehlung folgen, nicht nur allgemein als Risiko erwähnt werden.",
        "Behauptete Vorteile brauchen eine Verankerung in Fallfakten, nicht nur Plausibilität.",
    ],
    6: [
        "Synthese verlangt die integrierte Betrachtung früherer Teilentscheidungen; eine isolierte neue Strategie ist nur teilweise passend.",
        "Honoriere Integrations- und Kaskadenlogik (Konsequenzen einer Entscheidung für andere Teile) auch bei unkonventionellen, schlüssig begründeten Wegen.",
        "Vergleichende Begründung (warum diese Entscheidung riskanter/wichtiger als Alternativen ist) zählt mehr als bloßes Benennen.",
    ],
}


# ---------------------------------------------------------------------------
# Reine Helfer — JSON-Extraktion aus LLM-Antworten (ohne LLM testbar)
# ---------------------------------------------------------------------------

def extract_json_candidates(text: str) -> list[str]:
    """Drei Kandidaten in fester Reihenfolge: roh, ohne Code-Fences,
    Substring vom ersten '{' bis zum letzten '}'."""
    stripped = text.strip()
    candidates: list[str] = []

    if stripped:
        candidates.append(stripped)

    fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.IGNORECASE | re.DOTALL).strip()
    if fenced and fenced not in candidates:
        candidates.append(fenced)

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_slice = stripped[start:end + 1].strip()
        if json_slice and json_slice not in candidates:
            candidates.append(json_slice)

    return candidates


def parse_evaluation_payload(text: str) -> dict:
    """Erster Kandidat, der als JSON-Objekt parst, gewinnt."""
    for candidate in extract_json_candidates(text):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    raise ValueError("LLM evaluation response was not valid JSON")


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class RubricEvaluator:
    def __init__(self, api_key: str):
        self.client = OpenRouterClient(api_key=api_key)

    # -- Prompt-Bausteine ---------------------------------------------------

    def _make_tags(self, question: CaseQuestion) -> list[str]:
        return BLOOM_TAGS.get(question.bloom_level, ["analyse"])

    def _format_rubric_focus(self, rubric: QuestionRubric | None) -> str:
        if not rubric or not rubric.evaluation_focus:
            return "- Klare, fallbezogene Analyse mit nachvollziehbarer Entscheidung"
        return "\n".join(f"- {item}" for item in rubric.evaluation_focus)

    def _format_canvas_blocks(self, rubric: QuestionRubric | None) -> str:
        if not rubric or not rubric.required_canvas_blocks:
            return "- Keine spezifischen Canvas-Bausteine vorgegeben"

        lines = []
        for block in rubric.required_canvas_blocks:
            keywords = ", ".join(block.accepted_keywords)
            lines.append(
                f"- {block.block} ({block.label}): {block.expectation} "
                f"Signal-Keywords: {keywords}"
            )
        return "\n".join(lines)

    def _format_calibration_notes(self, question: CaseQuestion) -> str:
        """Zweistufige Kalibrierung: case-spezifische Anker haben Vorrang.

        Case-spezifische Anker (question.calibration_notes) stammen aus dem
        Case-Paket — für den Alpes-Bank-Case sind das die per Teacher-
        Alignment-Studie validierten Anker. Fehlen sie (neu generierte,
        noch nicht nachkalibrierte Cases), greifen generische Anker pro
        Bloom-Stufe.
        """
        if question.calibration_notes:
            return "\n".join(f"- {note}" for note in question.calibration_notes)

        notes = BLOOM_CALIBRATION_ANCHORS.get(question.bloom_level, [])
        if not notes:
            return "- Keine spezifischen Kalibrierungsanker vorhanden."
        return "\n".join(f"- {note}" for note in notes)

    def _build_prompt(
        self,
        *,
        case: Case,
        question: CaseQuestion,
        rubric: QuestionRubric | None,
        tags: list[str],
        answer_text: str,
    ) -> str:
        return EVALUATE_PROMPT.format(
            case_title=case.title,
            case_industry=case.industry,
            question_text=question.text,
            max_points=question.max_points,
            bloom_level=question.bloom_level,
            tags=", ".join(tags),
            rubric_focus=self._format_rubric_focus(rubric),
            canvas_blocks=self._format_canvas_blocks(rubric),
            calibration_notes=self._format_calibration_notes(question),
            answer=answer_text,
            mid_points=round(question.max_points * MID_BAND_FACTOR, 1),
            low_points=round(question.max_points * LOW_BAND_FACTOR, 1),
        )

    # -- LLM-Aufruf & Parsing -------------------------------------------------

    async def _request_repair(self, prompt: str, raw_text: str) -> str:
        return await self.client.complete(
            system=EVALUATOR_SYSTEM,
            messages=[
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": raw_text},
                {"role": "user", "content": REPAIR_PROMPT},
            ],
            max_tokens=EVALUATOR_MAX_TOKENS,
        )

    async def _evaluate_with_repair(
        self, *, prompt: str, submission_id: str, question_id: str, tags: list[str],
    ) -> dict:
        """Erst-Call → Parse → Repair-Call → technical_fallback."""
        text = await self.client.complete(
            system=EVALUATOR_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=EVALUATOR_MAX_TOKENS,
        )
        try:
            return parse_evaluation_payload(text)
        except ValueError:
            logger.warning(
                "evaluation_json_parse_failed",
                submission_id=submission_id,
                question_id=question_id,
                raw_preview=text[:500],
            )

        try:
            repaired_text = await self._request_repair(prompt, text)
            return parse_evaluation_payload(repaired_text)
        except ValueError:
            logger.error(
                "evaluation_json_repair_failed",
                submission_id=submission_id,
                question_id=question_id,
            )
            return self._fallback_payload(tags)

    def _fallback_payload(self, tags: list[str]) -> dict:
        return {
            "awarded_points": 0.0,
            "feedback": "Die automatische Auswertung konnte technisch nicht vollstaendig verarbeitet werden. Welche Kernargumente und Konsequenzen kannst du noch klarer strukturieren?",
            "learning_objective_tags": tags,
            "canvas_alignment_score": 0.0,
            "addressed_canvas_blocks": [],
            "missing_canvas_blocks": [],
            "canvas_rationale": "Technischer Fallback wegen ungueltiger Modellantwort.",
            "evaluation_status": "technical_fallback",
            "needs_human_review": True,
            "review_reason": "Die Modellantwort konnte auch nach Reparaturversuch nicht als valides JSON verarbeitet werden.",
            "judge_confidence": "low",
            "score_band": "unscored",
            "main_strengths": [],
            "main_penalties": ["Technischer Fallback; keine belastbare automatische Bewertung."],
        }

    # -- Sanitizing -----------------------------------------------------------

    def _sanitize_feedback(self, feedback: str) -> str:
        text = (feedback or "").strip()
        lower = text.lower()
        if not text or any(pattern in lower for pattern in DISALLOWED_FEEDBACK_PATTERNS):
            return (
                "Deine Antwort enthält erste Ansätze, aber die Begründung bleibt noch zu implizit. "
                "Welche Entscheidung triffst du genau, worauf stützt du sie im Case, und welche "
                "Konsequenz folgt daraus für das Unternehmen?"
            )
        return text

    def _sanitize_canvas_rationale(self, rationale: str | None) -> str | None:
        text = (rationale or "").strip()
        lower = text.lower()
        if any(pattern in lower for pattern in DISALLOWED_FEEDBACK_PATTERNS):
            return "Die Begründung bleibt bei den im Case sichtbaren Hinweisen und vermeidet nicht belegte Zusatzdetails."
        return text or None

    # -- Score-Bau ------------------------------------------------------------

    def _score_from_payload(
        self,
        *,
        question: CaseQuestion,
        rubric: QuestionRubric | None,
        data: dict,
        tags: list[str],
    ) -> QuestionScore:
        """Baut den QuestionScore; wirft TypeError/ValueError bei typ-
        ungültigen Zahlen im Payload (Aufrufer fällt dann auf den
        technical_fallback zurück)."""
        canvas_alignment_score = max(0.0, min(float(data.get("canvas_alignment_score", 0.0)), 1.0))
        awarded = max(0.0, min(float(data.get("awarded_points", 0.0)), question.max_points))

        needs_human_review = bool(data.get("needs_human_review", False))
        judge_confidence = str(data.get("judge_confidence", "") or "").lower() or None
        if judge_confidence == "low":
            needs_human_review = True
        review_reason = data.get("review_reason")

        return QuestionScore(
            question_id=question.question_id,
            bloom_level=question.bloom_level,
            max_points=question.max_points,
            awarded_points=awarded,
            feedback=self._sanitize_feedback(data.get("feedback", "")),
            learning_objective_tags=data.get("learning_objective_tags", tags),
            rubric_reference=question.rubric_reference,
            canvas_alignment_score=canvas_alignment_score,
            canvas_alignment_pct=round(canvas_alignment_score * 100, 1),
            required_canvas_blocks=(
                [block.block for block in rubric.required_canvas_blocks] if rubric else []
            ),
            addressed_canvas_blocks=[
                block for block in data.get("addressed_canvas_blocks", [])
                if isinstance(block, str)
            ],
            missing_canvas_blocks=[
                block for block in data.get("missing_canvas_blocks", [])
                if isinstance(block, str)
            ],
            canvas_rationale=self._sanitize_canvas_rationale(data.get("canvas_rationale")),
            evaluation_status=str(data.get("evaluation_status", "ok") or "ok"),
            needs_human_review=needs_human_review,
            review_reason=str(review_reason).strip() if review_reason else None,
            judge_confidence=judge_confidence,
            score_band=str(data.get("score_band", "") or "").lower() or None,
            main_strengths=_as_string_list(data.get("main_strengths")),
            main_penalties=_as_string_list(data.get("main_penalties")),
        )

    # -- Öffentliche API --------------------------------------------------------

    async def evaluate_question(
        self,
        *,
        submission: Submission,
        case: Case,
        question_id: str,
        answer_text: str,
    ) -> tuple[QuestionScore, QuestionRubric | None]:
        question = next((q for q in case.questions if q.question_id == question_id), None)
        if not question:
            raise ValueError(f"Unknown question_id: {question_id}")
        if not answer_text.strip():
            raise ValueError(f"Missing answer_text for question_id: {question_id}")

        rubric = load_question_rubric(question)
        tags = self._make_tags(question)
        prompt = self._build_prompt(
            case=case, question=question, rubric=rubric, tags=tags, answer_text=answer_text,
        )

        data = await self._evaluate_with_repair(
            prompt=prompt,
            submission_id=submission.submission_id,
            question_id=question_id,
            tags=tags,
        )

        try:
            score = self._score_from_payload(question=question, rubric=rubric, data=data, tags=tags)
        except (TypeError, ValueError):
            # Valides JSON, aber unbrauchbare Typen (z.B. awarded_points="acht")
            # → gleicher Weg wie Parse-Versagen: technischer Fallback.
            logger.error(
                "evaluation_payload_invalid_types",
                submission_id=submission.submission_id,
                question_id=question_id,
            )
            score = self._score_from_payload(
                question=question, rubric=rubric, data=self._fallback_payload(tags), tags=tags,
            )

        return score, rubric

    async def evaluate_submission(self, submission: Submission, case: Case) -> SubmissionResult:
        """Bewertet alle beantworteten Fragen PARALLEL (Reihenfolge stabil).

        Das globale LLM-Concurrency-Limit (backend/llm.py) begrenzt die
        tatsächliche Parallelität; ein Fehler in einer Frage bricht die
        Auswertung ab (Aufrufer antwortet 503, Retry möglich).
        """
        items = [
            (question_id, answer_text)
            for question_id, answer_text in submission.answers.items()
            if answer_text.strip()
        ]
        score_pairs = await asyncio.gather(*(
            self.evaluate_question(
                submission=submission, case=case,
                question_id=question_id, answer_text=answer_text,
            )
            for question_id, answer_text in items
        ))
        scores = [pair[0] for pair in score_pairs]

        result = self.result_from_scores(submission=submission, case=case, scores=scores)

        logger.info(
            "submission_evaluated",
            submission_id=submission.submission_id,
            case_id=case.case_id,
            total=result.total_points,
            max=result.max_points,
            pct=result.percentage,
            canvas_alignment_pct=result.canvas_alignment_pct,
            rubric_fit_pct=result.rubric_fit_pct,
            canvas_exemplar_candidate=result.canvas_exemplar_candidate,
        )

        return result

    def result_from_scores(
        self,
        *,
        submission: Submission,
        case: Case,
        scores: list[QuestionScore],
    ) -> SubmissionResult:
        questions_by_id = {q.question_id: q for q in case.questions}
        rubrics = [
            load_question_rubric(question)
            for score in scores
            if (question := questions_by_id.get(score.question_id)) is not None
            and question.rubric_reference
        ]

        total = sum(s.awarded_points for s in scores)
        maximum = sum(s.max_points for s in scores)
        pct = round((total / maximum * 100) if maximum > 0 else 0, 1)
        canvas_alignment_pct = round(
            (
                sum(s.canvas_alignment_score * s.max_points for s in scores) / maximum * 100
            ) if maximum > 0 else 0,
            1,
        )
        rubric_fit_pct = round(
            (pct * RUBRIC_FIT_SCORE_WEIGHT) + (canvas_alignment_pct * RUBRIC_FIT_CANVAS_WEIGHT), 1,
        )
        exemplar_candidate = self._canvas_exemplar_candidate(pct, canvas_alignment_pct, rubrics)

        return SubmissionResult(
            submission_id=submission.submission_id,
            case_id=submission.case_id,
            total_points=total,
            max_points=maximum,
            percentage=pct,
            canvas_alignment_pct=canvas_alignment_pct,
            rubric_fit_pct=rubric_fit_pct,
            canvas_exemplar_candidate=exemplar_candidate,
            canvas_summary=self._canvas_summary(canvas_alignment_pct, exemplar_candidate),
            scores=scores,
            overall_feedback=self._overall_feedback(pct),
        )

    # -- Aggregate ---------------------------------------------------------------

    def _canvas_exemplar_candidate(
        self,
        percentage: float,
        canvas_alignment_pct: float,
        rubrics: list[QuestionRubric | None],
    ) -> bool:
        thresholds = [rubric.exemplar_threshold_pct for rubric in rubrics if rubric]
        score_floors = [rubric.score_floor_pct for rubric in rubrics if rubric]
        canvas_threshold = min(thresholds) if thresholds else FALLBACK_EXEMPLAR_CANVAS_PCT
        score_threshold = min(score_floors) if score_floors else FALLBACK_EXEMPLAR_SCORE_PCT
        return percentage >= score_threshold and canvas_alignment_pct >= canvas_threshold

    def _overall_feedback(self, pct: float) -> str:
        if pct >= OVERALL_STRONG_PCT:
            return "Starke Analyse mit klaren Entscheidungen und gutem Case-Bezug. Prüfe, ob du Konsequenzen und Trade-offs überall explizit gemacht hast."
        if pct >= OVERALL_SOLID_PCT:
            return "Solide Grundlage. An mehreren Stellen fehlt die Verbindung zwischen Argument und Case-Kontext — was bedeutet das konkret für dieses Unternehmen?"
        if pct >= OVERALL_SURFACE_PCT:
            return "Die Analyse bleibt oft an der Oberfläche. Versuche, für jede Beobachtung eine Ursache und eine Konsequenz zu benennen."
        return "Die Antworten zeigen noch wenig betriebswirtschaftliches Denken. Fokussiere dich auf eine Herausforderung und arbeite sie vollständig durch."

    def _canvas_summary(self, canvas_alignment_pct: float, exemplar_candidate: bool) -> str:
        if exemplar_candidate:
            return "Die Lösung nutzt die relevanten Business-Model-Canvas-Bausteine stark und ist als Exemplar für spätere Auswertung geeignet."
        if canvas_alignment_pct >= CANVAS_BROAD_PCT:
            return "Die Lösung arbeitet mit mehreren passenden Canvas-Bausteinen, integriert sie aber noch nicht durchgängig."
        if canvas_alignment_pct >= CANVAS_PARTIAL_PCT:
            return "Einzelne Canvas-Bausteine werden erkennbar berührt, die Logik bleibt jedoch lückenhaft oder zu implizit."
        return "Die Antwort zeigt kaum belastbare Business-Model-Canvas-Logik."

    # -- Abwärtskompatible Methoden-Aliase (Tests/Skripte älterer Stände) --------

    def _extract_json_candidates(self, text: str) -> list[str]:
        return extract_json_candidates(text)

    def _parse_evaluation_payload(self, text: str, tags: list[str] | None = None) -> dict:
        return parse_evaluation_payload(text)
