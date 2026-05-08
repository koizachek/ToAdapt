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
    "porter", "five forces", "rbv", "vrio",
    "transaktionskostentheorie", "4p", "tce",
    "preiselastizität",   # nur TP3+, aber als Name verboten
]


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

Niemals: direkte Antworten, Musterlösungen, Framework-Namen.
Immer: Gegenfragen, die tiefer führen.""",

    AgentType.STRATEGIC: """Du bist ein strategischer Denkpartner in BWL A.

Deine Rolle: Studierende bei der Entscheidungslogik unterstützen.
Antworte kurz und klar in 2–4 Sätzen.
Verwende kein Markdown, keine Listen, keine Überschriften.
Hilf dabei, Optionen zu strukturieren, Trade-offs sichtbar zu machen und Konsequenzen zu durchdenken.

Niemals: Framework-Namen, direkte Empfehlungen, Musterlösungen.
Immer: "Was würde passieren, wenn...?" — "Welche Alternative hättest du?".""",

    AgentType.CONCEPTUAL: """Du bist ein konzeptueller Wissensbegleiter in BWL A.

Deine Rolle: Betriebswirtschaftliche Konzepte implizit zugänglich machen.
Wenn nach einem Begriff gefragt wird, antworte in genau zwei kurzen Teilen:
1. Erkläre den Begriff in 1–2 Sätzen einfach und präzise.
2. Erkläre in 1 Satz, welche Rolle er im aktuellen Case spielt.
Halte die Antwort insgesamt unter 90 Wörtern.
Verwende kein Markdown, keine Listen, keine Überschriften, keine Sonderzeichen-Deko.

Niemals: Framework-Namen nennen, Definitionen auswendig lernen lassen.
Immer: die Logik hinter dem Konzept verständlich machen.""",

    AgentType.PROCEDURAL: """Du bist ein Format- und Strukturbegleiter in BWL A.

Deine Rolle: Bei Darstellung und Struktur der Antwort helfen.
Antworte kurz und klar in 2–4 Sätzen.
Verwende kein Markdown, keine Listen, keine Überschriften.
Hilf dabei, die Antwort klar zu gliedern, das passende Format zu wählen und prägnanter zu werden.

Niemals: Inhaltliche Antworten, Framework-Namen.
Immer: strukturelle Hinweise, Fragen zur Klarheit.""",
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
    ])


def _select_agent(session: Session, user_message: str) -> str:
    """Wählt den passenden Agent-Typ basierend auf Session-State."""
    if _is_concept_request(user_message):
        return AgentType.CONCEPTUAL

    if not session.metacognitive_phase_complete:
        return AgentType.METACOGNITIVE

    lower = user_message.lower()
    if any(w in lower for w in ["entscheidung", "strategie", "option", "warum", "wählen"]):
        return AgentType.STRATEGIC
    if any(w in lower for w in ["konzept", "modell", "theorie"]):
        return AgentType.CONCEPTUAL
    if any(w in lower for w in ["format", "struktur", "folie", "memo", "schreiben"]):
        return AgentType.PROCEDURAL
    return AgentType.STRATEGIC


def _clean_response_text(text: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?---+\n?", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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
        return f"\nKERN-SPANNUNGSFELDER:\n{tensions}\n\nHÄUFIGE FEHLER VERMEIDEN:\n{mistakes}"
    except Exception:
        return ""


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

        guidance = _load_case_guidance(session.case_id)
        system = (
            f"{AGENT_PROMPTS[agent_type]}\n\n"
            f"CASE-KONTEXT (TP{tp} — {TP_CONFIGS[tp]['name']}):\n{case_context}"
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
            text = (
                "Ich möchte dich bei diesem Schritt lieber mit einer Gegenfrage begleiten: "
                "Was ist das Kernproblem, das du hier lösen willst — und welche zwei "
                "möglichen Wege siehst du?"
            )

        # Metacognitive Phase als complete markieren nach erster Antwort
        if agent_type == AgentType.METACOGNITIVE and session.message_count >= 1:
            session.metacognitive_phase_complete = True

        logger.info("agent_response", agent=agent_type, tp=tp, msg_count=session.message_count)
        return agent_type, text
