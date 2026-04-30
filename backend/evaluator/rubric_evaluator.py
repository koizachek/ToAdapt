"""Rubric-Evaluator — Bewertet Studierenden-Antworten gegen Bloom-Lernziele.

Prinzipien:
- Pfadoffenheit: mehrere valide Antwortpfade möglich
- Kein Answer-Reveal: Feedback scaffolded, nicht lösungsgebend
- Bloom-Stufen-Scoring: separate Scores pro Lernziel-Dimension
"""

import json
import uuid
from datetime import datetime

import anthropic
import structlog

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

Du antwortest AUSSCHLIESSLICH mit einem validen JSON-Array. Kein Text davor oder danach."""


EVALUATE_PROMPT = """Bewerte die folgende Studierenden-Antwort auf die Prüfungsfrage.

CASE-KONTEXT: {case_title} ({case_industry})

FRAGE: {question_text}
Maximale Punkte: {max_points}
Bloom-Stufe: {bloom_level}
Lernziel-Tags: {tags}

ANTWORT DES STUDIERENDEN:
{answer}

Antworte mit einem JSON-Objekt:
{{
  "awarded_points": <float, 0 bis {max_points}>,
  "feedback": "<scaffolded feedback, max 80 Wörter>",
  "learning_objective_tags": ["<tag1>", "<tag2>"]
}}

Vergabe-Leitlinien:
- {max_points} Punkte: Klare Entscheidung, 2 starke Argumente, Case-Bezug, Konsequenzen benannt
- {mid_points} Punkte: Entscheidung vorhanden, Begründung teilweise, wenig Case-Bezug
- {low_points} Punkte: Analyse bleibt an der Oberfläche, keine Ursache-Wirkung, generisch
- 0 Punkte: Keine verwertbare Antwort"""


class RubricEvaluator:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def _make_tags(self, question: CaseQuestion) -> list[str]:
        base = {
            2: ["verstehen", "identifizieren"],
            3: ["anwenden", "transfer"],
            4: ["analysieren", "wirkungskette", "stakeholder"],
            5: ["evaluieren", "trade-off", "kpi"],
            6: ["synthese", "integration", "reflexion"],
        }
        return base.get(question.bloom_level, ["analyse"])

    async def evaluate_submission(self, submission: Submission, case: Case) -> SubmissionResult:
        scores: list[QuestionScore] = []

        questions_by_id = {q.question_id: q for q in case.questions}

        for question_id, answer_text in submission.answers.items():
            question = questions_by_id.get(question_id)
            if not question or not answer_text.strip():
                continue

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
                answer=answer_text,
                mid_points=mid,
                low_points=low,
            )

            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=512,
                system=EVALUATOR_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )

            data = json.loads(response.content[0].text)

            scores.append(QuestionScore(
                question_id=question_id,
                bloom_level=question.bloom_level,
                max_points=question.max_points,
                awarded_points=min(data["awarded_points"], question.max_points),
                feedback=data["feedback"],
                learning_objective_tags=data.get("learning_objective_tags", tags),
            ))

        total = sum(s.awarded_points for s in scores)
        maximum = sum(s.max_points for s in scores)
        pct = round((total / maximum * 100) if maximum > 0 else 0, 1)

        overall = self._overall_feedback(pct)

        logger.info(
            "submission_evaluated",
            submission_id=submission.submission_id,
            total=total,
            max=maximum,
            pct=pct,
        )

        return SubmissionResult(
            submission_id=submission.submission_id,
            case_id=submission.case_id,
            total_points=total,
            max_points=maximum,
            percentage=pct,
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
