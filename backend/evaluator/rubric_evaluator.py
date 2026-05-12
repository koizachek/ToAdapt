"""Rubric-Evaluator — Bewertet Studierenden-Antworten gegen Bloom-Lernziele.

Prinzipien:
- Pfadoffenheit: mehrere valide Antwortpfade möglich
- Kein Answer-Reveal: Feedback scaffolded, nicht lösungsgebend
- Bloom-Stufen-Scoring: separate Scores pro Lernziel-Dimension
"""

import json

import structlog

from backend.evaluator.rubric_loader import QuestionRubric, load_question_rubric
from backend.llm import OpenRouterClient
from backend.models.case import Case, CaseQuestion
from backend.models.submission import QuestionScore, Submission, SubmissionResult

logger = structlog.get_logger(__name__)

EVALUATOR_SYSTEM = """Du bist ein Bewertungsassistent für BWL A an der Universität St. Gallen.

Du bewertest Studierenden-Antworten auf Basis von pfadoffenen Rubrics.

BEWERTUNGSPRINZIPIEN:
- Es gibt keine einzig richtige Antwort. Jede schlüssig begründete Entscheidung kann volle Punktzahl erreichen.
- Bewertet wird die Qualität des Denkens, nicht die sprachliche Glätte.
- Framework-Namen müssen NICHT genannt werden — die Logik muss angewendet werden.
- Generische Aussagen ohne ON/Case-Bezug erhalten keine Spitzenpunkte.
- Dein Feedback ist scaffolded: Du zeigst Denkrichtungen auf, gibst aber keine Musterlösung.

FEEDBACK-FORMAT (pro Frage):
- Was gut funktioniert (1–2 Sätze)
- Was fehlt oder schwach ist (1–2 Sätze, als Frage formuliert)
- Keine direkte Antwort nennen

Wenn eine Canvas-Rubric vorliegt, prüfst du explizit, ob die relevanten Business-Model-Canvas-Bausteine inhaltlich angewendet wurden.
Keywords sind nur Signale. Entscheidend ist die Qualität der Anwendung auf den Fall.

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
  "canvas_rationale": "<kurze Begründung, max 50 Wörter>"
}}

Vergabe-Leitlinien:
- {max_points} Punkte: Klare Entscheidung, 2 starke Argumente, Case-Bezug, Konsequenzen benannt
- {mid_points} Punkte: Entscheidung vorhanden, Begründung teilweise, wenig Case-Bezug
- {low_points} Punkte: Analyse bleibt an der Oberfläche, keine Ursache-Wirkung, generisch
- 0 Punkte: Keine verwertbare Antwort

Canvas-Scoring:
- 1.0: Die relevanten Canvas-Bausteine werden korrekt, fallbezogen und integriert angewendet.
- 0.5: Einige passende Bausteine werden angesprochen, aber nur teilweise oder oberflächlich.
- 0.0: Keine belastbare Canvas-Logik erkennbar."""


class RubricEvaluator:
    def __init__(self, api_key: str):
        self.client = OpenRouterClient(api_key=api_key)

    def _make_tags(self, question: CaseQuestion) -> list[str]:
        base = {
            2: ["verstehen", "identifizieren"],
            3: ["anwenden", "transfer"],
            4: ["analysieren", "wirkungskette", "stakeholder"],
            5: ["evaluieren", "trade-off", "kpi"],
            6: ["synthese", "integration", "reflexion"],
        }
        return base.get(question.bloom_level, ["analyse"])

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

    def _canvas_exemplar_candidate(
        self,
        percentage: float,
        canvas_alignment_pct: float,
        rubrics: list[QuestionRubric | None],
    ) -> bool:
        thresholds = [rubric.exemplar_threshold_pct for rubric in rubrics if rubric]
        score_floors = [rubric.score_floor_pct for rubric in rubrics if rubric]
        canvas_threshold = min(thresholds) if thresholds else 80.0
        score_threshold = min(score_floors) if score_floors else 75.0
        return percentage >= score_threshold and canvas_alignment_pct >= canvas_threshold

    async def evaluate_submission(self, submission: Submission, case: Case) -> SubmissionResult:
        scores: list[QuestionScore] = []
        used_rubrics: list[QuestionRubric | None] = []

        questions_by_id = {q.question_id: q for q in case.questions}

        for question_id, answer_text in submission.answers.items():
            question = questions_by_id.get(question_id)
            if not question or not answer_text.strip():
                continue

            rubric = load_question_rubric(question)
            used_rubrics.append(rubric)
            tags = self._make_tags(question)
            mid = round(question.max_points * 0.55, 1)
            low = round(question.max_points * 0.25, 1)

            prompt = EVALUATE_PROMPT.format(
                case_title=case.title,
                case_industry=case.industry,
                question_text=question.text,
                max_points=question.max_points,
                bloom_level=question.bloom_level,
                tags=", ".join(tags),
                rubric_focus=self._format_rubric_focus(rubric),
                canvas_blocks=self._format_canvas_blocks(rubric),
                answer=answer_text,
                mid_points=mid,
                low_points=low,
            )

            text = await self.client.complete(
                system=EVALUATOR_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
            )
            data = json.loads(text)
            canvas_alignment_score = max(0.0, min(float(data.get("canvas_alignment_score", 0.0)), 1.0))
            required_canvas_blocks = [
                block.block for block in rubric.required_canvas_blocks
            ] if rubric else []
            addressed_canvas_blocks = [
                block for block in data.get("addressed_canvas_blocks", [])
                if isinstance(block, str)
            ]
            missing_canvas_blocks = [
                block for block in data.get("missing_canvas_blocks", [])
                if isinstance(block, str)
            ]

            scores.append(QuestionScore(
                question_id=question_id,
                bloom_level=question.bloom_level,
                max_points=question.max_points,
                awarded_points=min(data["awarded_points"], question.max_points),
                feedback=data["feedback"],
                learning_objective_tags=data.get("learning_objective_tags", tags),
                rubric_reference=question.rubric_reference,
                canvas_alignment_score=canvas_alignment_score,
                canvas_alignment_pct=round(canvas_alignment_score * 100, 1),
                required_canvas_blocks=required_canvas_blocks,
                addressed_canvas_blocks=addressed_canvas_blocks,
                missing_canvas_blocks=missing_canvas_blocks,
                canvas_rationale=data.get("canvas_rationale"),
            ))

        total = sum(s.awarded_points for s in scores)
        maximum = sum(s.max_points for s in scores)
        pct = round((total / maximum * 100) if maximum > 0 else 0, 1)
        canvas_alignment_pct = round(
            (
                sum(s.canvas_alignment_score * s.max_points for s in scores) / maximum * 100
            ) if maximum > 0 else 0,
            1,
        )
        rubric_fit_pct = round((pct * 0.7) + (canvas_alignment_pct * 0.3), 1)
        exemplar_candidate = self._canvas_exemplar_candidate(
            pct,
            canvas_alignment_pct,
            used_rubrics,
        )

        overall = self._overall_feedback(pct)
        canvas_summary = self._canvas_summary(canvas_alignment_pct, exemplar_candidate)

        logger.info(
            "submission_evaluated",
            submission_id=submission.submission_id,
            total=total,
            max=maximum,
            pct=pct,
            canvas_alignment_pct=canvas_alignment_pct,
            rubric_fit_pct=rubric_fit_pct,
            canvas_exemplar_candidate=exemplar_candidate,
        )

        return SubmissionResult(
            submission_id=submission.submission_id,
            case_id=submission.case_id,
            total_points=total,
            max_points=maximum,
            percentage=pct,
            canvas_alignment_pct=canvas_alignment_pct,
            rubric_fit_pct=rubric_fit_pct,
            canvas_exemplar_candidate=exemplar_candidate,
            canvas_summary=canvas_summary,
            scores=scores,
            overall_feedback=overall,
        )

    def _overall_feedback(self, pct: float) -> str:
        if pct >= 80:
            return "Starke Analyse mit klaren Entscheidungen und gutem Case-Bezug. Prüfe, ob du Konsequenzen und Trade-offs überall explizit gemacht hast."
        if pct >= 60:
            return "Solide Grundlage. An mehreren Stellen fehlt die Verbindung zwischen Argument und Case-Kontext — was bedeutet das konkret für dieses Unternehmen?"
        if pct >= 40:
            return "Die Analyse bleibt oft an der Oberfläche. Versuche, für jede Beobachtung eine Ursache und eine Konsequenz zu benennen."
        return "Die Antworten zeigen noch wenig betriebswirtschaftliches Denken. Fokussiere dich auf eine Herausforderung und arbeite sie vollständig durch."

    def _canvas_summary(self, canvas_alignment_pct: float, exemplar_candidate: bool) -> str:
        if exemplar_candidate:
            return "Die Lösung nutzt die relevanten Business-Model-Canvas-Bausteine stark und ist als Exemplar für spätere Auswertung geeignet."
        if canvas_alignment_pct >= 70:
            return "Die Lösung arbeitet mit mehreren passenden Canvas-Bausteinen, integriert sie aber noch nicht durchgängig."
        if canvas_alignment_pct >= 40:
            return "Einzelne Canvas-Bausteine werden erkennbar berührt, die Logik bleibt jedoch lückenhaft oder zu implizit."
        return "Die Antwort zeigt kaum belastbare Business-Model-Canvas-Logik."
