"""Formale Vorprüfung einer Abgabe — wird gemeldet, nie bewertet.

Vorgaben aus ``formal_checks`` der Rubric: Zeichengrenzen je Folie
(inklusive Leerzeichen), Code-Muster ``TPn-UEGxx-SGy``, Dateinamens-Muster
``TPn_UEGxx_SGy.pptx``, ganze Sätze (Heuristik). Alle Ergebnisse sind reine
Hinweise für die ÜGL (``report_only_never_grade``).
"""

from __future__ import annotations

import re

from backend.briefings.extraction import ExtractedSubmission
from backend.briefings.rubrics import BriefingRubric

_SENTENCE_END = re.compile(r"[.!?…»\")]\s*$")


def full_sentences_hint(text: str) -> str | None:
    """Heuristik: Anteil der Absätze, die mit Satzzeichen enden.

    Liefert einen Hinweistext, wenn Stichpunkt-Fragmente wahrscheinlich
    sind; sonst None. Keine Bewertung — nur ein Beobachtungspunkt.
    """
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    ended = sum(1 for line in lines if _SENTENCE_END.search(line))
    share = ended / len(lines)
    if share < 0.5:
        return f"Nur {ended} von {len(lines)} Absätzen enden mit Satzzeichen — Stichpunkt-Verdacht."
    return None


def formal_checks(sub: ExtractedSubmission, rubric: BriefingRubric, target_tp: int) -> dict:
    kd = sub.kenndaten
    code = kd.code or ""
    result: dict = {
        "filename": sub.filename,
        "format": sub.format,
        "template_detected": sub.template_detected,
        "slide_count": sub.slide_count,
        "baustein1_chars": sub.baustein1_chars,
        "baustein1_max": rubric.max_chars("baustein1"),
        "baustein1_within_limit": sub.baustein1_chars <= rubric.max_chars("baustein1"),
        "baustein2_chars": sub.baustein2_chars,
        "baustein2_max": rubric.max_chars("baustein2"),
        "baustein2_within_limit": sub.baustein2_chars <= rubric.max_chars("baustein2"),
        "code": code or None,
        "code_source": kd.source or None,
        "code_valid": bool(code) and bool(rubric.code_regex.fullmatch(code)),
        "code_matches_tp": (kd.tp == target_tp) if kd.tp else True,
        "filename_valid": bool(rubric.filename_regex.fullmatch(sub.filename)),
        "members_filled": kd.members_filled,
        "notes": list(sub.notes),
    }
    hints = [
        h for h in (full_sentences_hint(sub.baustein1), full_sentences_hint(sub.baustein2)) if h
    ]
    result["full_sentences_hint"] = " ".join(hints) if hints else None
    if kd.tp and kd.tp != target_tp:
        result["notes"].append(
            f"Der Code nennt Touchpoint {kd.tp}, hochgeladen wurde für Touchpoint {target_tp}."
        )
    if not sub.template_detected and sub.format == "pptx":
        result["notes"].append("Die Kenndaten-Felder der offiziellen Vorlage wurden nicht gefunden.")
    return result
