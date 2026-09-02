"""Briefing-Generator: verdichtet EINE Stammgruppen-Abgabe je Baustein.

Produkt 1 der KI-Pipeline (KI_Paket, Output-Spezifikation): je Baustein
Kernposition (ein Satz), tragende Argumente (höchstens zwei), dünne Stellen
(höchstens zwei, als Ansatz für eine Rückfrage) sowie eine Einschätzung in
Prosa entlang der Kriterien. Zusätzlich — intern, nie im Briefing — die
Niveau-Einstufung je Kriterium (ueberzeugend / tragfaehig / ansatzweise)
mit Begründung, damit die Kursleitung die Kalibrierung des Judge prüfen kann.

Robustheits-Kette wie beim RubricEvaluator: Erst-Call → JSON-Parse
(3 Kandidaten) → Repair-Call → technical_fallback (Platzhaltertexte,
needs_human_review=True). Danach Leitplanken-Nachprüfung
(``backend/briefings/guardrails.py``) auf alle tutor-sichtbaren Felder.

Der System-Prompt ist je Touchpoint byte-identisch (Rubric + Case-Kapitel +
Beispielabgaben) und wird per Prompt-Caching (``cache_system=True``) über
den ganzen Batch wiederverwendet.
"""

from __future__ import annotations

import re

import structlog

from backend.briefings.extraction import ExtractedSubmission
from backend.briefings.guardrails import apply_guardrails, sanitize_swiss
from backend.briefings.rubrics import BriefingRubric, case_context_for_tp
from backend.evaluator.rubric_evaluator import REPAIR_PROMPT, parse_evaluation_payload
from backend.llm import OpenRouterClient

logger = structlog.get_logger(__name__)

BRIEFING_MAX_TOKENS = 2200
MAX_ITEMS = 2  # tragende Argumente / dünne Stellen je Baustein

NO_CONTENT_TEXT = "Zu diesem Baustein liegt kein Text vor."
FALLBACK_TEXT = (
    "Die automatische Verdichtung konnte technisch nicht erstellt werden — "
    "bitte die Abgabe direkt lesen."
)

BRIEFING_SYSTEM_TEMPLATE = """Du bereitest für die Übungsgruppenleitung (ÜGL) des Kurses {course} ein Briefing zu einer Stammgruppen-Abgabe vor.

KONTEXT
Touchpoint {tp} übt formativ am Running Case ON (Kapitel {chapter}) die Denkoperation, die in der Klausur in Aufgabe {exam_ref} am unbekannten Fall summativ geprüft wird. Das Briefing dient der ÜGL zur Vorbereitung des Gesprächs (Oxford-Tutorial: nachfragen, nicht bewerten). Die Abgabe ist eine Behauptung; erst das Gespräch zeigt, ob die Gruppe trägt, was sie geschrieben hat.
Massgebliche Case-Stellen: {case_references}

LEITPLANKEN (hart, gelten ohne Ausnahme)
- Keine Punkte, keine Noten, keine notenähnlichen Stufen, keine Prozentwerte als Bewertung. Auch keine Etiketten wie "Niveau: tragfähig" im Briefing-Text.
- Keine Musterlösung: Nie benennen, welche Entscheidung richtig gewesen wäre. Jede Wahl (jede Herausforderung, jeder Stakeholder, jede Strategie, jeder Kanal) ist zulässig; beurteilt wird ausschliesslich, ob die Begründung trägt.
- Kein Vergleich mit anderen Gruppen. Du siehst nur diese eine Abgabe.
- Nutze nur Informationen aus dem Fallmaterial und der Abgabe. Erfinde keine Zahlen, Akteure oder Ereignisse.
- Sprache: Schweizer Standarddeutsch (ss statt ß), sachlich, knapp, ganze Sätze.
- Nenne keine Namen von Studierenden, auch wenn sie im Text stehen.
{extra_guardrails}
RUBRIC (Kriterien mit Niveau-Deskriptoren; identisch mit dem Klausur-Bewertungsraster, hier punktfrei angewendet)
{rubric_block}

FALLMATERIAL (Running Case ON)
{case_context}

KALIBRIERUNGSANKER (konstruierte Beispielabgaben mit Einordnung durch die Kursleitung — keine Musterlösungen; jede andere Wahl kann dasselbe Niveau erreichen)
{examples_block}

AUFGABE
Du erhältst den Text der Abgabe je Baustein. Erstelle je Baustein:
1. "kernposition": EIN Satz — wofür sich die Gruppe entschieden hat (ihre Behauptung), in eigenen Worten.
2. "tragende_argumente": höchstens {max_items} Argumente, die die Position wirklich stützen (fallbezogen, konkret). Leere Liste, wenn nichts trägt.
3. "duenne_stellen": höchstens {max_items} Stellen, an denen die Begründung dünn bleibt — jeweils formuliert als Ansatz für eine Rückfrage der ÜGL (z.B. "Woran macht die Gruppe fest, dass …?"). Leere Liste, wenn nichts dünn ist.
4. "einschaetzung": zwei bis vier Sätze Fliesstext entlang der Kriterien: wo trägt die Begründung, wo bleibt sie dünn. Ohne Stufenbezeichnungen, ohne Punkte, ohne Empfehlung einer anderen Entscheidung.
5. "kriterien": INTERN (nicht Teil des Briefings) — für jedes Kriterium der Rubric ein Objekt mit "name" (exakt wie in der Rubric), "niveau" (ueberzeugend | tragfaehig | ansatzweise) und "begruendung" (ein Satz, warum genau dieses Niveau).

Ist der Text eines Bausteins leer, setze kernposition auf "{no_content}", beide Listen leer, einschaetzung auf "{no_content}" und kriterien auf eine leere Liste.

Antworte NUR mit einem JSON-Objekt dieser Form:
{{
  "baustein1": {{
    "kernposition": "<ein Satz>",
    "tragende_argumente": ["<Argument>", "<Argument>"],
    "duenne_stellen": ["<Rückfrage-Ansatz>", "<Rückfrage-Ansatz>"],
    "einschaetzung": "<2–4 Sätze Prosa>",
    "kriterien": [{{"name": "<Kriterium>", "niveau": "ueberzeugend|tragfaehig|ansatzweise", "begruendung": "<ein Satz>"}}]
  }},
  "baustein2": {{ ...gleiche Struktur... }},
  "judge_confidence": "high|medium|low",
  "needs_human_review": <true|false>,
  "review_reason": "<nur falls needs_human_review=true, sonst null>"
}}
Markiere needs_human_review=true bei niedriger Sicherheit, wenn der Text unvollständig oder fehlextrahiert wirkt, oder wenn die Abgabe offensichtlich nicht zum Arbeitsauftrag passt."""

TP5_EXTRA_GUARDRAIL = (
    "- Touchpoint 5: Die Gruppe verweist auf eigene Vorentscheidungen aus den "
    "Touchpoints 2 bis 4. Beurteile ausschliesslich die Binnenkohärenz der "
    "vorliegenden Antwort — nie die Qualität dieser Vorentscheidungen.\n"
)

SUBMISSION_TEMPLATE = """ABGABE {code}

=== Baustein 1 · {title1} (Folie 2) ===
{text1}

=== Baustein 2 · {title2} (Folie 3) ===
{text2}

Erstelle jetzt das JSON."""


def _rubric_block(rubric: BriefingRubric) -> str:
    lines: list[str] = []
    for b in rubric.bausteine:
        lines.append(f"{b.key.upper()} · {b.title} (Folie {b.slide}, Klausur {b.exam_ref})")
        for c in b.criteria:
            lines.append(f"- Kriterium «{c.name}»")
            lines.append(f"  ueberzeugend: {c.ueberzeugend}")
            lines.append(f"  tragfaehig: {c.tragfaehig}")
            lines.append(f"  ansatzweise: {c.ansatzweise}")
        if b.typical_weaknesses:
            lines.append(f"  {b.typical_weaknesses}")
        lines.append("")
    return "\n".join(lines).strip()


def _examples_block(rubric: BriefingRubric) -> str:
    if not rubric.examples:
        return "(keine Beispielabgaben hinterlegt)"
    parts: list[str] = []
    for level in rubric.levels:
        ex = rubric.examples.get(level)
        if not ex:
            continue
        parts.append(
            f"Beispielabgabe · {level}\n"
            f"Folie 2: {ex.slide2}\n"
            f"Folie 3: {ex.slide3}\n"
            f"Einordnung: {ex.calibration_note}"
        )
    return "\n\n".join(parts)


def build_system_prompt(rubric: BriefingRubric) -> str:
    """Byte-identisch je TP → Prompt-Caching über den ganzen Batch."""
    return BRIEFING_SYSTEM_TEMPLATE.format(
        course=rubric.course,
        tp=rubric.tp,
        chapter=rubric.case_chapter or "?",
        exam_ref=", ".join(rubric.exam_ref) or f"A{rubric.tp}",
        case_references=rubric.case_references or "siehe Kapitel",
        extra_guardrails=TP5_EXTRA_GUARDRAIL if rubric.tp == 5 else "",
        rubric_block=_rubric_block(rubric),
        case_context=case_context_for_tp(rubric.tp) or "(Case-Kapitel nicht hinterlegt)",
        examples_block=_examples_block(rubric),
        max_items=MAX_ITEMS,
        no_content=NO_CONTENT_TEXT,
    )


def build_user_prompt(rubric: BriefingRubric, sub: ExtractedSubmission) -> str:
    b1 = rubric.baustein("baustein1")
    b2 = rubric.baustein("baustein2")
    return SUBMISSION_TEMPLATE.format(
        code=sub.kenndaten.code or sub.filename,
        title1=b1.title,
        text1=sub.baustein1.strip() or "(leer)",
        title2=b2.title,
        text2=sub.baustein2.strip() or "(leer)",
    )


# ---------------------------------------------------------------------------
# Ergebnis-Normalisierung
# ---------------------------------------------------------------------------

def _strings(value: object, limit: int | None = None) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [str(v).strip() for v in value if str(v).strip()]
    return items[:limit] if limit else items


def _normalize_level(value: object, allowed: list[str]) -> str:
    text = re.sub(r"[^a-z]", "", str(value or "").lower().replace("ä", "ae").replace("ü", "ue"))
    for level in allowed:
        if text == level:
            return level
    return "unbestimmt"


def _empty_baustein(text: str) -> dict:
    return {
        "kernposition": text,
        "tragende_argumente": [],
        "duenne_stellen": [],
        "einschaetzung": text,
    }


def _normalize_payload(
    rubric: BriefingRubric, sub: ExtractedSubmission, data: dict
) -> tuple[dict, dict, list[str]]:
    """Trennt tutor-sichtbares Briefing von interner Einstufung und wendet
    die Leitplanken an. Rückgabe (briefing, assessment, guardrail_hits)."""
    briefing: dict = {}
    assessment: dict = {}
    hits: list[str] = []

    for b in rubric.bausteine:
        raw = data.get(b.key) if isinstance(data.get(b.key), dict) else {}
        text = getattr(sub, b.key, "")
        if not text.strip():
            briefing[b.key] = _empty_baustein(NO_CONTENT_TEXT)
            assessment[b.key] = {"kriterien": [], "keine_abgabe": True}
            continue

        visible = {
            "kernposition": str(raw.get("kernposition", "") or "").strip() or FALLBACK_TEXT,
            "tragende_argumente": _strings(raw.get("tragende_argumente"), MAX_ITEMS),
            "duenne_stellen": _strings(raw.get("duenne_stellen"), MAX_ITEMS),
            "einschaetzung": str(raw.get("einschaetzung", "") or "").strip() or FALLBACK_TEXT,
        }
        cleaned: dict = {}
        for key, value in visible.items():
            value_clean, value_hits = apply_guardrails(value)
            cleaned[key] = value_clean
            hits.extend(h for h in value_hits if h not in hits)
        briefing[b.key] = cleaned

        allowed_names = [c.name for c in b.criteria]
        kriterien = []
        for item in raw.get("kriterien", []) if isinstance(raw.get("kriterien"), list) else []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if name not in allowed_names:
                # tolerante Zuordnung (Gross-/Kleinschreibung, Whitespace)
                match = [n for n in allowed_names if n.lower() == name.lower()]
                if not match:
                    continue
                name = match[0]
            kriterien.append({
                "name": name,
                "niveau": _normalize_level(item.get("niveau"), rubric.levels),
                "begruendung": sanitize_swiss(str(item.get("begruendung", "")).strip()),
            })
        missing = [n for n in allowed_names if n not in {k["name"] for k in kriterien}]
        assessment[b.key] = {"kriterien": kriterien, "fehlende_kriterien": missing}

    confidence = str(data.get("judge_confidence", "") or "").lower() or None
    needs_review = bool(data.get("needs_human_review", False)) or confidence == "low"
    review_reason = data.get("review_reason")
    assessment["judge_confidence"] = confidence
    assessment["needs_human_review"] = needs_review
    assessment["review_reason"] = sanitize_swiss(str(review_reason).strip()) if review_reason else None
    return briefing, assessment, hits


def fallback_result(rubric: BriefingRubric, sub: ExtractedSubmission, reason: str) -> dict:
    briefing = {}
    assessment = {}
    for b in rubric.bausteine:
        text = getattr(sub, b.key, "")
        briefing[b.key] = _empty_baustein(FALLBACK_TEXT if text.strip() else NO_CONTENT_TEXT)
        assessment[b.key] = {"kriterien": [], "keine_abgabe": not text.strip()}
    assessment.update({
        "judge_confidence": "low",
        "needs_human_review": True,
        "review_reason": reason,
    })
    return {
        "briefing": briefing,
        "assessment": assessment,
        "evaluation_status": "technical_fallback",
        "needs_human_review": True,
        "review_reason": reason,
        "guardrail_hits": [],
    }


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class BriefingGenerator:
    def __init__(self, api_key: str):
        self.client = OpenRouterClient(api_key=api_key)

    async def _call(self, *, system: str, messages: list[dict[str, str]]) -> str:
        return await self.client.complete(
            system=system,
            messages=messages,
            max_tokens=BRIEFING_MAX_TOKENS,
            cache_system=True,
        )

    async def generate(self, *, briefing_id: str, rubric: BriefingRubric, sub: ExtractedSubmission) -> dict:
        """Erzeugt Briefing + interne Einstufung; nie Exception aus der
        LLM-/Parse-Kette — schlimmstenfalls technical_fallback."""
        if not sub.has_content:
            result = fallback_result(rubric, sub, "Kein Text in der Abgabe gefunden.")
            result["evaluation_status"] = "no_content"
            return result

        system = build_system_prompt(rubric)
        user = build_user_prompt(rubric, sub)

        try:
            text = await self._call(system=system, messages=[{"role": "user", "content": user}])
        except Exception as exc:
            logger.error("briefing_llm_failed", briefing_id=briefing_id, error=str(exc))
            return fallback_result(rubric, sub, "LLM-Aufruf fehlgeschlagen.")

        data: dict | None = None
        try:
            data = parse_evaluation_payload(text)
        except ValueError:
            logger.warning("briefing_json_parse_failed", briefing_id=briefing_id, raw_preview=text[:300])
            try:
                repaired = await self._call(
                    system=system,
                    messages=[
                        {"role": "user", "content": user},
                        {"role": "assistant", "content": text},
                        {"role": "user", "content": REPAIR_PROMPT},
                    ],
                )
                data = parse_evaluation_payload(repaired)
            except Exception:
                logger.error("briefing_json_repair_failed", briefing_id=briefing_id)
                return fallback_result(
                    rubric, sub, "Modellantwort war auch nach Reparaturversuch kein valides JSON."
                )

        briefing, assessment, hits = _normalize_payload(rubric, sub, data or {})
        needs_review = bool(assessment.get("needs_human_review")) or bool(hits)
        review_reason = assessment.get("review_reason")
        if hits and not review_reason:
            review_reason = "Leitplanken-Prüfung hat Textteile zurückgehalten: " + ", ".join(hits)
        if hits:
            logger.warning("briefing_guardrail_triggered", briefing_id=briefing_id, hits=hits)
        return {
            "briefing": briefing,
            "assessment": assessment,
            "evaluation_status": "ok",
            "needs_human_review": needs_review,
            "review_reason": review_reason,
            "guardrail_hits": hits,
        }
