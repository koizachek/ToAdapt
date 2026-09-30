"""Formale Vorprüfung einer Abgabe — wird gemeldet, nie bewertet.

Vorgaben aus ``formal_checks`` der Rubric: Zeichengrenzen je Folie
(inklusive Leerzeichen), Code-Muster ``TPn-UEGxx-SGy``, Dateinamens-Muster
``TPn_UEGxx_SGy.pptx``. Alle Ergebnisse sind reine Hinweise für die ÜGL
(``report_only_never_grade``). Der frühere "Stichpunkt-Verdacht" (Anteil
der Absätze mit Satzzeichen) ist auf Owner-Entscheidung vom 2026-09-30
entfernt: Er zählte Überschriften und Beschriftungen mit und schlug bei
gestalteten Folien in der Hälfte der Fälle an.
"""

from __future__ import annotations

from backend.briefings.extraction import ExtractedSubmission
from backend.briefings.rubrics import BriefingRubric

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
        "notes": list(sub.notes),
    }
    if kd.tp and kd.tp != target_tp:
        result["notes"].append(
            f"Das Deckblatt nennt Touchpoint {kd.tp}, ausgewertet wurde für Touchpoint {target_tp}."
        )
    return result
