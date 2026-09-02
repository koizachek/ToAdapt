"""Leitplanken-Nachprüfung für KI-Briefings (und später KI-Feedback).

Die Rubrics der Kursleitung schreiben für beide KI-Produkte vor:
no_points_or_grades, no_model_solution, no_group_comparison,
swiss_standard_german_ss (ss statt ß). Das LLM wird per Prompt darauf
verpflichtet; diese Nachprüfung ist die zweite Verteidigungslinie (gleiche
Philosophie wie ``guardrail_check`` im Chat-Orchestrator): Ein Treffer
ersetzt das betroffene Textfeld durch einen neutralen Hinweis und markiert
das Briefing zur manuellen Sicht — nie stilles Durchwinken.

Bewusst nicht verboten sind die Wörter der Niveau-Deskriptoren (trägt,
dünn, überzeugend …) in Prosa — genau so soll die Einschätzung formuliert
sein. Verboten sind Skalen und Etiketten (Punkte, Noten, Prozent, "Stufe 2",
"Niveau: tragfähig").
"""

from __future__ import annotations

import re

GUARDRAIL_PLACEHOLDER = (
    "[Von der Leitplanken-Prüfung zurückgehalten — bitte die Abgabe direkt lesen.]"
)

# (label, pattern) — Labels landen im Log und im Datensatz (guardrail_hits).
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # "an diesem Punkt" ist legitime Prosa — nur Zahl+Punkt(e), Plural und
    # Punktzahl gelten als Skala. Prozentangaben werden NICHT geprüft: Sie
    # sind im Fallmaterial häufig (z.B. Kundenanteile) und in Argumenten
    # legitim.
    # "Punkte" als Listeneinträge ("die vier Punkte aus Abschnitt 2.5") sind
    # legitim — nur Zahl+Punkte oder Vergabe-Verben gelten als Bewertung.
    ("points", re.compile(r"\b\d+([.,]\d+)?\s*(?:von\s*\d+\s*)?punkte?\b", re.IGNORECASE)),
    ("points", re.compile(r"\bpunktzahl\b|\bpunktevergabe\b|\bpunktabzug\b", re.IGNORECASE)),
    ("points", re.compile(r"\b(erh(ä|ae)lt|erhalten|erreicht|bekommt|bekommen|vergeben|verdient|kostet)\s+(\w+\s+){0,3}punkte?\b", re.IGNORECASE)),
    ("grades", re.compile(r"\bnote[n]?\b|\bbenotung\b|\bnotenstufe|\bbewertungsstufe", re.IGNORECASE)),
    ("scale", re.compile(r"\b(stufe|level|niveau)\s*[:=]?\s*([1-5]\b|ueberzeugend|überzeugend|tragf(ä|ae)hig|ansatzweise)", re.IGNORECASE)),
    ("scale", re.compile(r"\b(ueberzeugend|überzeugend|tragf(ä|ae)hig|ansatzweise)\s*/\s*(ueberzeugend|überzeugend|tragf(ä|ae)hig|ansatzweise)", re.IGNORECASE)),
    ("model_solution", re.compile(r"\bmusterl(ö|oe)sung", re.IGNORECASE)),
    ("model_solution", re.compile(r"\b(die|der|das)\s+(richtige|korrekte)\s+(antwort|entscheidung|wahl|l(ö|oe)sung|stakeholder|herausforderung|strategie|option|kanal|preis)", re.IGNORECASE)),
    ("model_solution", re.compile(r"\bh(ä|ae)tte[n]?\s+(die gruppe\s+)?(stattdessen\s+)?.{0,60}?\b(w(ä|ae)hlen|entscheiden|nehmen)\s+(sollen|m(ü|ue)ssen)", re.IGNORECASE)),
    ("model_solution", re.compile(r"\b(besser|richtiger)\s+w(ä|ae)re\s+(es\s+)?gewesen", re.IGNORECASE)),
    ("model_solution", re.compile(r"\bfalsche[rsn]?\s+(wahl|entscheidung|antwort|stakeholder|strategie)", re.IGNORECASE)),
    ("group_comparison", re.compile(r"\b(andere|übrigen|uebrigen|restlichen|anderen)\s+(stamm)?gruppen?\b", re.IGNORECASE)),
    ("group_comparison", re.compile(r"\bim vergleich (zu|mit) (den |der )?(anderen|übrigen|uebrigen)?\s*(stamm)?gruppen?\b", re.IGNORECASE)),
    ("group_comparison", re.compile(r"\b(als|wie) (die )?(stamm)?gruppe\s+(SG\s?)?[1-8]\b", re.IGNORECASE)),
]


def sanitize_swiss(text: str) -> str:
    """Schweizer Standarddeutsch: ß → ss."""
    return (text or "").replace("ß", "ss").replace("ẞ", "SS")


def check_briefing_text(text: str) -> list[str]:
    """Liefert die Labels aller verletzten Leitplanken (leer = sauber)."""
    hits: list[str] = []
    for label, pattern in _PATTERNS:
        if pattern.search(text or "") and label not in hits:
            hits.append(label)
    return hits


def apply_guardrails(value: str | list[str]) -> tuple[str | list[str], list[str]]:
    """Wendet ss-Regel an und ersetzt Treffer durch den Platzhalter.

    Rückgabe (bereinigter Wert, Trefferlabels). Listen werden elementweise
    geprüft — ein sauberes Argument überlebt, ein verletzendes wird ersetzt.
    """
    if isinstance(value, list):
        out: list[str] = []
        hits: list[str] = []
        for item in value:
            cleaned, item_hits = apply_guardrails(str(item))
            out.append(str(cleaned))
            hits.extend(h for h in item_hits if h not in hits)
        return out, hits
    text = sanitize_swiss(str(value))
    hits = check_briefing_text(text)
    if hits:
        return GUARDRAIL_PLACEHOLDER, hits
    return text, []
