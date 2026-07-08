"""Formatives Live-Feedback („Denkanstoß") — sokratisch, ohne Punkte.

Ziel: Studierende bekommen VOR der Abgabe Hinweise, wo ihr Denken noch
Lücken hat — ohne Lösung, ohne Bewertung, ohne Framework-Namen. Bewusst
begrenzt (max. Abrufe pro Frage in der Route), damit niemand iterativ auf
den Judge hinoptimiert. Jede Ausgabe läuft durch guardrail_check.
"""

from __future__ import annotations

import structlog

from backend.agents.orchestrator import guardrail_check
from backend.llm import OpenRouterClient
from backend.models.case import Case, CaseQuestion

logger = structlog.get_logger(__name__)

MAX_FEEDBACK_PER_QUESTION = 2

FORMATIVE_SYSTEM = """Du bist ein sokratischer Lernbegleiter für BWL-Studierende.
Du liest einen Antwort-ENTWURF zu einer Case-Frage und hilfst beim Weiterdenken.

REGELN (hart):
- KEINE Punkte, KEINE Bewertung, KEINE Note, KEIN Urteil wie "gut/schlecht".
- KEINE Lösung, keine Musterformulierung, keine inhaltlichen Antworten.
- KEINE Theorie- oder Framework-Namen.
- Stelle 2–3 kurze Rückfragen oder Denkanstöße, die auf LÜCKEN im Entwurf
  zeigen (fehlende Begründung, fehlender Case-Bezug, fehlende Konsequenz,
  unklare Entscheidung) — formuliert als Fragen an die Studierenden.
- Beziehe dich nur auf den Case-Kontext und den Entwurf. Erfinde nichts.
- Maximal 80 Wörter. Keine Listen-Symbole, kein Markdown, keine Emojis."""

FORMATIVE_SYSTEM_EN = """You are a Socratic learning companion for business students.
You read a DRAFT answer to a case question and help the student think further.

RULES (hard):
- NO points, NO grading, NO verdict like "good/bad".
- NO solutions, no model phrasing, no content answers.
- NO theory or framework names.
- Ask 2-3 short follow-up questions or prompts that point at GAPS in the
  draft (missing justification, missing case reference, missing consequence,
  unclear decision) — phrased as questions to the student.
- Refer only to the case context and the draft. Invent nothing.
- Maximum 80 words. No list symbols, no markdown, no emojis."""

FORMATIVE_PROMPT = """CASE-KONTEXT:
{case_context}

FRAGE AN DIE STUDIERENDEN:
{question_text}

ANTWORT-ENTWURF:
{answer_text}

Gib 2–3 sokratische Denkanstöße zu den Lücken dieses Entwurfs."""

FORMATIVE_PROMPT_EN = """CASE CONTEXT:
{case_context}

QUESTION FOR THE STUDENT:
{question_text}

DRAFT ANSWER:
{answer_text}

Give 2-3 Socratic prompts about the gaps in this draft."""

FALLBACK_DE = (
    "Lies deinen Entwurf noch einmal laut: Welche Entscheidung triffst du, "
    "womit begründest du sie aus dem Case, und was folgt daraus für das Unternehmen?"
)
FALLBACK_EN = (
    "Read your draft aloud once more: What decision do you make, how do you "
    "justify it from the case, and what does it imply for the company?"
)


async def generate_formative_feedback(
    *,
    api_key: str,
    case: Case,
    question: CaseQuestion,
    answer_text: str,
) -> str:
    """Erzeugt einen Denkanstoß; fällt bei Guardrail-Verstoß auf eine feste Frage zurück."""
    language = case.language or "de"
    system = FORMATIVE_SYSTEM_EN if language == "en" else FORMATIVE_SYSTEM
    template = FORMATIVE_PROMPT_EN if language == "en" else FORMATIVE_PROMPT

    case_context = f"{case.title}\n{case.tagline}\n" + "\n".join(
        s.content[:400] for s in case.sections[:2]
    )
    prompt = template.format(
        case_context=case_context,
        question_text=question.text,
        answer_text=answer_text.strip()[:4000],
    )

    client = OpenRouterClient(api_key=api_key)
    text = await client.complete(
        system=system,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=220,
    )
    text = text.strip()

    tp = question.phase or case.target_tp or 1
    ok, reason = guardrail_check(text, tp)
    if not ok:
        logger.warning(
            "formative_feedback_guardrail_triggered",
            case_id=case.case_id, question_id=question.question_id, reason=reason,
        )
        return FALLBACK_EN if language == "en" else FALLBACK_DE
    return text
