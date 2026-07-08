"""Automatische Qualitäts-Checks für Cases vor der Freigabe.

Prüft die harten Lehrdesign-Constraints (keine Framework-Namen, kein Bezug
auf ON Running/NORDIC HOME) als Fehler und Struktur-Erwartungen (Fragenzahl,
Bloom-Abdeckung, Punktesumme) als Warnungen. Fehler blockieren die Freigabe,
Warnungen sind Hinweise für die Lehrperson.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from backend.config.tp_configs import TP_CONFIGS
from backend.models.case import Case

# Kurs-reservierte Cases dürfen in generierten Cases nicht vorkommen.
RESERVED_CASE_TERMS = ["ON Running", "NORDIC HOME"]


class ValidationIssue(BaseModel):
    level: str          # "error" | "warning"
    code: str
    message: str
    location: str = ""  # z.B. "section:s2", "question:q1"


class CaseValidationReport(BaseModel):
    ok: bool            # True = keine Fehler (Warnungen sind erlaubt)
    issues: list[ValidationIssue] = Field(default_factory=list)


def _contains_term(text: str, term: str) -> bool:
    return bool(re.search(rf"(?<![\w-]){re.escape(term)}(?![\w-])", text, re.IGNORECASE))


def _iter_texts(case: Case):
    yield "title", case.title
    yield "tagline", case.tagline
    for s in case.sections:
        yield f"section:{s.section_id}", f"{s.title}\n{s.content}"
    for e in case.exhibits:
        yield f"exhibit:{e.exhibit_id}", f"{e.title}\n{e.content}"
    for q in case.questions:
        yield f"question:{q.question_id}", q.text


def validate_case(case: Case) -> CaseValidationReport:
    issues: list[ValidationIssue] = []
    tp_cfg = TP_CONFIGS.get(case.target_tp)
    forbidden = list(tp_cfg["forbidden_framework_names"]) if tp_cfg else []
    for q in case.questions:
        for name in q.forbidden_framework_names:
            if name not in forbidden:
                forbidden.append(name)

    # Fehler: verbotene Framework-Namen im Studierenden-sichtbaren Text.
    for location, text in _iter_texts(case):
        for name in forbidden:
            if _contains_term(text, name):
                issues.append(ValidationIssue(
                    level="error",
                    code="forbidden_framework_name",
                    message=f"Framework-Name „{name}“ darf im Case-Text nicht vorkommen.",
                    location=location,
                ))
        for term in RESERVED_CASE_TERMS:
            if _contains_term(text, term):
                issues.append(ValidationIssue(
                    level="error",
                    code="reserved_case_reference",
                    message=f"Bezug auf reservierten Kurs-Case „{term}“.",
                    location=location,
                ))

    # Fehler: leere Pflichtfelder.
    if not case.title.strip():
        issues.append(ValidationIssue(level="error", code="empty_field", message="Titel fehlt.", location="title"))
    if not case.tagline.strip():
        issues.append(ValidationIssue(level="error", code="empty_field", message="Tagline fehlt.", location="tagline"))
    if not case.sections:
        issues.append(ValidationIssue(level="error", code="empty_field", message="Case hat keine Sections.", location="sections"))
    if not case.questions:
        issues.append(ValidationIssue(level="error", code="empty_field", message="Case hat keine Fragen.", location="questions"))
    for s in case.sections:
        if not s.content.strip():
            issues.append(ValidationIssue(level="error", code="empty_field", message="Section ohne Inhalt.", location=f"section:{s.section_id}"))
    for q in case.questions:
        if not q.text.strip():
            issues.append(ValidationIssue(level="error", code="empty_field", message="Frage ohne Text.", location=f"question:{q.question_id}"))

    # Warnungen: Struktur-Erwartungen.
    if not 4 <= len(case.sections) <= 6:
        issues.append(ValidationIssue(
            level="warning", code="section_count",
            message=f"{len(case.sections)} Sections (erwartet 4–6).", location="sections",
        ))
    if len(case.exhibits) < 3:
        issues.append(ValidationIssue(
            level="warning", code="exhibit_count",
            message=f"{len(case.exhibits)} Exhibits (erwartet 3–5).", location="exhibits",
        ))

    # Warnung: Fragen ohne eingebettetes Bewertungspaket fallen auf die
    # tp{n}_rubric.json-Dateien zurück — die sind auf den Alpes-Bank-Case
    # kalibriert und passen inhaltlich nicht zu neuen Cases.
    for q in case.questions:
        if not q.required_canvas_blocks:
            issues.append(ValidationIssue(
                level="warning", code="missing_embedded_rubric",
                message="Frage hat keine eigenen required_canvas_blocks — der Judge nutzt den "
                        "Alpes-Bank-kalibrierten Datei-Fallback. Canvas-Blöcke im Editor ergänzen.",
                location=f"question:{q.question_id}",
            ))
        else:
            for block in q.required_canvas_blocks:
                if not block.accepted_keywords:
                    issues.append(ValidationIssue(
                        level="warning", code="canvas_block_without_keywords",
                        message=f"Canvas-Baustein „{block.label}“ hat keine Signal-Keywords — "
                                "Abdeckungs-Anzeige und Judge-Signal bleiben dafür blind.",
                        location=f"question:{q.question_id}",
                    ))

    if tp_cfg:
        expected_blooms = set(tp_cfg["bloom_levels"])
        covered = {q.bloom_level for q in case.questions}
        missing = expected_blooms - covered
        if missing:
            issues.append(ValidationIssue(
                level="warning", code="bloom_coverage",
                message=f"Bloom-Stufen {sorted(missing)} werden von keiner Frage abgedeckt "
                        f"(TP{case.target_tp} erwartet {sorted(expected_blooms)}).",
                location="questions",
            ))

    from backend.cases.generator import TP_GENERATION_PARAMS
    gen_params = TP_GENERATION_PARAMS.get(case.target_tp)
    if gen_params:
        total = sum(q.max_points for q in case.questions)
        if total != gen_params["total_points"]:
            issues.append(ValidationIssue(
                level="warning", code="total_points",
                message=f"Punktesumme {total} (erwartet {gen_params['total_points']}).",
                location="questions",
            ))

    ok = not any(i.level == "error" for i in issues)
    return CaseValidationReport(ok=ok, issues=issues)
