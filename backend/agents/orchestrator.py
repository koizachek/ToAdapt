"""Agent-Orchestrator — individuelles Scaffolding, kein Answer-Reveal.

Sequenz (empirisch validiert):
    1. Metacognitive Agent  — Reflexion, Planung
    2. Strategic Agent      — Ansatz, Trade-offs
    3. Conceptual Agent     — Domänenwissen (implizit)
    4. Procedural Agent     — Format, Struktur

Der Orchestrator entscheidet anhand von Session-State und Message-Content,
welcher Agent antwortet.
"""

import re
import unicodedata

import structlog

from backend.config.tp_configs import TP_CONFIGS
from backend.llm import OpenRouterClient
from backend.models.message import AgentType
from backend.models.session import Session

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Guardrail-Check
# ---------------------------------------------------------------------------

FORBIDDEN_PATTERNS = [
    "die antwort ist",
    "die lösung lautet",
    "du solltest schreiben",
    "hier ist die musterlösung",
    "hier ist eine mögliche antwort",
    "the answer is",
    "the solution is",
    "you should write",
    "here is the model answer",
    "here is a possible answer",
    "porter", "five forces", "rbv", "vrio",
    "transaktionskostentheorie", "4p", "tce",
    "preiselastizität",   # nur TP3+, aber als Name verboten
    "transaction cost theory",
    "price elasticity",
]

SLANG_PATTERNS = [
    "haha",
    "diggi",
    "hau rein",
    "whatever",
    "du packst das",
]

RECOMMENDATION_PATTERNS = [
    "erste herausforderung könnte sein",
    "zweite herausforderung könnte sein",
    "nimm einen der drei",
    "nimm den",
    "wähle den",
    "waehle den",
    "tamara sollte",
    "sie sollte den",
    "ich empfehle",
    "der website-chatbot ist",
    "der website chatbot ist",
    "der e-mail-assistent ist",
    "der email-assistent ist",
    "der email assistent ist",
    "first challenge could be",
    "second challenge could be",
    "choose the",
    "pick the",
    "tamara should",
    "she should choose",
    "i recommend",
    "the website chatbot is",
    "the email assistant is",
]

CASE_SPECULATION_PATTERNS = [
    "finma",
    "swiss hosting",
    "azure switzerland",
    "microsoft",
]


def _contains_emoji(text: str) -> bool:
    for char in text:
        if unicodedata.category(char) == "So":
            return True
    return False


def _contains_direct_recommendation(text: str) -> bool:
    lower = text.lower()
    if any(pattern in lower for pattern in RECOMMENDATION_PATTERNS):
        return True

    recommendation_regexes = [
        r"\berste herausforderung\b.{0,80}\bkönnte sein\b",
        r"\berste herausforderung\b.{0,80}\bkoennte sein\b",
        r"\b(tamara|du|sie)\s+sollte\b.{0,40}\b(chatbot|e-mail-assistent|email-assistent|wissens-copilot)\b",
        r"\b(wähle|waehle|nimm)\b.{0,20}\b(chatbot|e-mail-assistent|email-assistent|wissens-copilot)\b",
        r"\bfirst challenge\b.{0,80}\bcould be\b",
        r"\b(tamara|you|she)\s+should\b.{0,40}\b(chatbot|email assistant|knowledge copilot)\b",
        r"\b(choose|pick)\b.{0,20}\b(chatbot|email assistant|knowledge copilot)\b",
    ]
    return any(re.search(pattern, lower, flags=re.DOTALL) for pattern in recommendation_regexes)


def guardrail_check(text: str, tp: int) -> tuple[bool, str]:
    """Gibt (ok, reason) zurück. False = Text verletzt Guardrail."""
    lower = text.lower()
    # Phasen-spezifisch verbotene Framework-Namen
    forbidden = TP_CONFIGS[tp].get("forbidden_framework_names", [])
    for name in forbidden:
        if name.lower() in lower:
            return False, f"framework_name_dropped: {name}"
    for pattern in FORBIDDEN_PATTERNS:
        if pattern in lower:
            return False, f"direct_answer_pattern: {pattern}"
    if any(pattern in lower for pattern in SLANG_PATTERNS):
        return False, "style_contains_slang"
    if _contains_emoji(text):
        return False, "style_contains_emoji"
    if _contains_direct_recommendation(text):
        return False, "direct_recommendation_or_template"
    if any(pattern in lower for pattern in CASE_SPECULATION_PATTERNS):
        return False, "case_speculation_outside_context"
    return True, ""


# ---------------------------------------------------------------------------
# Agent-Prompts
# ---------------------------------------------------------------------------

AGENT_PROMPTS = {
    AgentType.METACOGNITIVE: """Du bist ein metacognitiver Lernbegleiter in BWL A.

Deine Rolle: Studierende zum Nachdenken über ihren eigenen Denkprozess anregen.
Antworte kurz und klar in 2–4 Sätzen.
Stelle höchstens eine Gegenfrage.
Verwende kein Markdown, keine Listen, keine Überschriften.
Der Ton darf zugänglich und locker sein, aber nicht slangig, nicht anbiedernd und ohne Emojis.

Niemals: direkte Antworten, Musterlösungen, Framework-Namen, fertige Formulierungen zum Abschreiben.
Immer: Gegenfragen, die tiefer führen.""",

    AgentType.STRATEGIC: """Du bist ein strategischer Denkpartner in BWL A.

Deine Rolle: Studierende bei der Entscheidungslogik unterstützen.
Antworte kurz und klar in 2–4 Sätzen.
Verwende kein Markdown, keine Listen, keine Überschriften.
Hilf dabei, Optionen zu strukturieren, Trade-offs sichtbar zu machen und Konsequenzen zu durchdenken.
Der Ton darf zugänglich und locker sein, aber nicht slangig, nicht kumpelhaft und ohne Emojis.

Niemals: Framework-Namen, direkte Empfehlungen, Musterlösungen, konkrete Use-Case-Auswahl, ausformulierte Zwei-Satz-Antworten oder Sätze wie "erste Herausforderung könnte sein...".
Wenn mehrere Use Cases oder Optionen diskutiert werden, nenne Kriterien und Spannungen, aber entscheide nicht für den Studierenden.
Nutze nur Informationen, die im Case-Kontext oder in der aktuellen Nachricht explizit vorkommen. Ergänze keine plausiblen Zusatzdetails wie Regulatoren, Anbieter, Hosting-Setups oder Vertragsklauseln, wenn sie nicht im Material stehen.
Immer: "Was würde passieren, wenn...?" — "Welche Alternative hättest du?".""",

    AgentType.CONCEPTUAL: """Du bist ein konzeptueller Wissensbegleiter in BWL A.

Deine Rolle: Betriebswirtschaftliche Konzepte implizit zugänglich machen.
Wenn nach einem Begriff gefragt wird, antworte in genau zwei kurzen Teilen:
1. Erkläre den Begriff in 1–2 Sätzen einfach und präzise.
2. Erkläre in 1 Satz, welche Rolle er im aktuellen Case spielt.
Halte die Antwort insgesamt unter 90 Wörtern.
Verwende kein Markdown, keine Listen, keine Überschriften, keine Sonderzeichen-Deko.
Der Ton darf klar und nahbar sein, aber nicht slangig und ohne Emojis.

Niemals: Framework-Namen nennen, Definitionen auswendig lernen lassen, nicht belegte Fall-Details ergänzen.
Wenn eine Rolle im Case nicht explizit im Material steht, formuliere vorsichtig mit "könnte" oder verweise auf sichtbare Spannungen statt Details zu erfinden.
Immer: die Logik hinter dem Konzept verständlich machen.""",

    AgentType.PROCEDURAL: """Du bist ein Format- und Strukturbegleiter in BWL A.

Deine Rolle: Bei Darstellung und Struktur der Antwort helfen.
Antworte kurz und klar in 2–4 Sätzen.
Verwende kein Markdown, keine Listen, keine Überschriften.
Hilf dabei, die Antwort klar zu gliedern, das passende Format zu wählen und prägnanter zu werden.
Der Ton darf locker sein, aber nicht slangig und ohne Emojis.

Niemals: Inhaltliche Antworten, Framework-Namen, ausformulierte Musterantworten.
Immer: strukturelle Hinweise, Fragen zur Klarheit.""",
}

AGENT_PROMPTS_EN = {
    AgentType.METACOGNITIVE: """You are a metacognitive learning companion for Business Administration A.

Your role: encourage students to reflect on their own thinking process.
Answer briefly and clearly in 2-4 sentences.
Ask at most one follow-up question.
Do not use Markdown, lists, or headings.
The tone may be approachable, but not slangy, not ingratiating, and without emojis.

Never: direct answers, model solutions, framework names, ready-made wording to copy.
Always: ask questions that lead to deeper thinking.""",

    AgentType.STRATEGIC: """You are a strategic thinking partner for Business Administration A.

Your role: support students with decision logic.
Answer briefly and clearly in 2-4 sentences.
Do not use Markdown, lists, or headings.
Help structure options, make trade-offs visible, and think through consequences.
The tone may be approachable, but not slangy, not buddy-like, and without emojis.

Never: framework names, direct recommendations, model solutions, a concrete use-case choice, fully written answer templates, or sentences such as "the first challenge could be...".
When several use cases or options are discussed, name criteria and tensions, but do not decide for the student.
Use only information explicitly present in the case context or in the current message. Do not add plausible extra details such as regulators, providers, hosting setups, or contract clauses if they are not in the material.
Always: ask what would happen if something changed, or what alternative the student would have.""",

    AgentType.CONCEPTUAL: """You are a conceptual knowledge companion for Business Administration A.

Your role: make business concepts implicitly accessible.
When asked about a term, answer in exactly two short parts:
1. Explain the term simply and precisely in 1-2 sentences.
2. Explain in 1 sentence what role it plays in the current case.
Keep the whole answer under 90 words.
Do not use Markdown, lists, headings, or decorative special characters.
The tone may be clear and approachable, but not slangy and without emojis.

Never: name framework names, make students memorize definitions, or add unsupported case details.
If a role in the case is not explicit in the material, phrase it cautiously with "could" or refer to visible tensions instead of inventing details.
Always: make the logic behind the concept understandable.""",

    AgentType.PROCEDURAL: """You are a format and structure companion for Business Administration A.

Your role: help with presentation and answer structure.
Answer briefly and clearly in 2-4 sentences.
Do not use Markdown, lists, or headings.
Help the student structure the answer clearly, choose an appropriate format, and become more concise.
The tone may be relaxed, but not slangy and without emojis.

Never: content answers, framework names, or fully written model answers.
Always: structural guidance and questions about clarity.""",
}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def _is_concept_request(user_message: str) -> bool:
    lower = user_message.lower()
    return any(w in lower for w in [
        "erklär",
        "begriff",
        "was bedeutet",
        "einordnen",
        "rolle im case",
        "rolle im kontext",
        "rolle im gesamtkontext",
        "explain",
        "term",
        "what does",
        "what means",
        "role in the case",
        "role in context",
    ])


def _select_agent(session: Session, user_message: str) -> str:
    """Wählt den passenden Agent-Typ basierend auf Session-State."""
    if _is_concept_request(user_message):
        return AgentType.CONCEPTUAL

    if not session.metacognitive_phase_complete:
        return AgentType.METACOGNITIVE

    lower = user_message.lower()
    if any(w in lower for w in [
        "entscheidung",
        "strategie",
        "option",
        "warum",
        "wählen",
        "decision",
        "strategy",
        "option",
        "why",
        "choose",
        "trade-off",
        "tradeoff",
    ]):
        return AgentType.STRATEGIC
    if any(w in lower for w in ["konzept", "modell", "theorie", "concept", "model", "theory"]):
        return AgentType.CONCEPTUAL
    if any(w in lower for w in [
        "format",
        "struktur",
        "folie",
        "memo",
        "schreiben",
        "structure",
        "slide",
        "write",
        "writing",
    ]):
        return AgentType.PROCEDURAL
    return AgentType.STRATEGIC


def _clean_response_text(text: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?---+\n?", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _guardrail_fallback(agent_type: str, language: str = "de") -> str:
    if language == "en":
        if agent_type == AgentType.CONCEPTUAL:
            return (
                "Briefly: focus on the basic logic of the term and then ask which visible tension "
                "in the case it describes. What role does the term play here for the decision or "
                "the business model?"
            )
        if agent_type == AgentType.PROCEDURAL:
            return (
                "Keep your answer concise: first the core claim, then the reasoning, then the consequence. "
                "Which one statement is truly central right now?"
            )
        return (
            "I will stay with the thinking structure rather than giving you a finished direction: "
            "which two criteria or tensions are clearly supported by the case, and how would they "
            "change your decision?"
        )

    if agent_type == AgentType.CONCEPTUAL:
        return (
            "Kurz erklärt: Konzentriere dich auf die Grundlogik des Begriffs und frage dich dann, "
            "welche sichtbare Spannung im Case damit beschrieben wird. Welche Rolle spielt der Begriff "
            "hier für die Entscheidung oder das Geschäftsmodell?"
        )
    if agent_type == AgentType.PROCEDURAL:
        return (
            "Halte deine Antwort knapp: erst die Kernbehauptung, dann die Begründung, dann die Konsequenz. "
            "Welche eine Aussage ist bei dir gerade wirklich zentral?"
        )
    return (
        "Ich bleibe hier lieber bei der Denkstruktur statt dir eine fertige Richtung vorzugeben: "
        "Welche zwei Kriterien oder Spannungen sind aus dem Case sicher belegt, und wie würden sie "
        "deine Entscheidung verändern?"
    )


def _load_case_guidance(case_id: str) -> str:
    """Lädt case-spezifisches Agent-Guidance JSON falls vorhanden."""
    import json
    from pathlib import Path
    p = Path(__file__).parent.parent / "cases" / "pool" / f"{case_id}-agent.json"
    if not p.exists():
        return ""
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        g = data.get("agent_guidance", {})
        tensions = "\n".join(f"- {t}" for t in g.get("key_tensions", []))
        mistakes  = "\n".join(f"- {m}" for m in g.get("common_mistakes", []))
        if case_id.endswith("-en"):
            return f"\nKEY TENSIONS:\n{tensions}\n\nCOMMON MISTAKES TO AVOID:\n{mistakes}"
        return f"\nKERN-SPANNUNGSFELDER:\n{tensions}\n\nHÄUFIGE FEHLER VERMEIDEN:\n{mistakes}"
    except Exception:
        return ""


def _session_language(session: Session) -> str:
    if session.experiment and session.experiment.metadata.get("language") == "en":
        return "en"
    if session.case_id.endswith("-en"):
        return "en"
    return "de"


class AgentOrchestrator:
    def __init__(self, api_key: str):
        self.client = OpenRouterClient(api_key=api_key)

    async def respond(
        self,
        session: Session,
        user_message: str,
        history: list[dict],
        case_context: str,
    ) -> tuple[str, str]:
        """Gibt (agent_type, response_text) zurück."""

        agent_type = _select_agent(session, user_message)
        tp = session.tp_phase
        language = _session_language(session)
        agent_prompts = AGENT_PROMPTS_EN if language == "en" else AGENT_PROMPTS

        guidance = _load_case_guidance(session.case_id)
        context_header = "CASE CONTEXT" if language == "en" else "CASE-KONTEXT"
        system = (
            f"{agent_prompts[agent_type]}\n\n"
            f"{context_header} (TP{tp} - {TP_CONFIGS[tp]['name']}):\n{case_context}"
            f"{guidance}"
        )

        messages = history + [{"role": "user", "content": user_message}]

        text = await self.client.complete(
            system=system,
            messages=messages,
            max_tokens=220 if agent_type == AgentType.CONCEPTUAL else 320,
        )
        text = _clean_response_text(text)

        ok, reason = guardrail_check(text, tp)
        if not ok:
            logger.warning("guardrail_triggered", reason=reason, agent=agent_type)
            text = _guardrail_fallback(agent_type, language)

        # Metacognitive Phase als complete markieren nach erster Antwort
        if agent_type == AgentType.METACOGNITIVE and session.message_count >= 1:
            session.metacognitive_phase_complete = True

        logger.info("agent_response", agent=agent_type, tp=tp, msg_count=session.message_count, language=language)
        return agent_type, text
