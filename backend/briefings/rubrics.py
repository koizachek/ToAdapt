"""Rubric-Config der KI-Pipeline je Touchpoint (Briefing + Feedback).

Quelle: ``backend/config/ki_rubrics/ki_rubrics_tp{n}.json`` — die von der
Kursleitung gelieferten Rubrics (BWL A HS26, KI_Paket vom 2026-08-28) mit
Kriterien, Niveau-Deskriptoren, Leitplanken, formalen Checks, Output-Schemas
und drei konstruierten Beispielabgaben je Touchpoint (Kalibrierungsanker).

Dazu der Running Case ON als Kontext für den Judge
(``backend/config/ki_rubrics/case/kapitel_{a..e}.md``, Nummerierung wie in
den Rubric-Referenzen: Kapitel A = Abschnitt 2, B = 3, C = 4, D = 5, E = 6)
und die Vorlagentexte der offiziellen Abgabevorlagen
(``template_texts.json``), damit die Extraktion Vorlagentext von
Studierendentext trennen kann.

Diese Config ist ausschliesslich tutor-/pipeline-seitig — nichts davon ist
studierendensichtbar. Der Reserved-Term-Check in ``backend/cases/validator.py``
(ON Running / NORDIC HOME) betrifft nur AI-generierte Mini-Cases des
Studierenden-Tools und bleibt unberührt.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

KI_RUBRICS_DIR = Path(__file__).resolve().parent.parent / "config" / "ki_rubrics"
CASE_DIR = KI_RUBRICS_DIR / "case"

SUPPORTED_TPS: tuple[int, ...] = (1, 2, 3, 4, 5)

# Case-Kapitel je Touchpoint (Blaupause, Abschnitt 9).
TP_CHAPTER: dict[int, str] = {1: "a", 2: "b", 3: "c", 4: "d", 5: "e"}

# Kapitelübergreifende Referenzstellen aus den Rubric-Metadaten:
# TP2 verweist zusätzlich auf Abschnitt 2.8 (Patentablauf CloudTec, Kapitel A).
TP_EXTRA_SECTIONS: dict[int, list[tuple[str, str]]] = {2: [("a", "2.8")]}

# Termine je Touchpoint (KI_Paket, Kopfzeile: Abgabe Di 23:59, Termin Do).
# Nur für Briefing-Kopf/Anzeige — der Studierenden-Terminplan (TP_SCHEDULE in
# backend/config/tp_configs.py) bleibt davon bewusst getrennt.
BRIEFING_SCHEDULE: dict[int, dict[str, date]] = {
    1: {"abgabe": date(2026, 9, 29), "termin": date(2026, 10, 2)},
    2: {"abgabe": date(2026, 10, 20), "termin": date(2026, 10, 23)},
    3: {"abgabe": date(2026, 11, 24), "termin": date(2026, 11, 27)},
    4: {"abgabe": date(2026, 12, 8), "termin": date(2026, 12, 11)},
    5: {"abgabe": date(2026, 12, 15), "termin": date(2026, 12, 18)},
}

# Feed-forward-Sätze je Touchpoint (KI_Paket, Abschnitt "Formale Vorprüfung /
# Feed-forward") — Anker für den Schlussabsatz des KI-Feedbacks. TP5 ohne die
# Punktangabe der Klausur (Leitplanke no_points_or_grades gilt auch dort).
FEED_FORWARD: dict[int, str] = {
    1: "In Touchpoint 2 wird auf dieser Analyse entschieden; in der Klausur ist dies Aufgabe 1 am unbekannten Fall.",
    2: "In Touchpoint 3 wird der Marktzugang an der heutigen Strategie gemessen; in der Klausur ist dies Aufgabe 2 am unbekannten Fall.",
    3: "In Touchpoint 4 geht es um Eigenleistung und Lieferkette; in der Klausur ist dies Aufgabe 3, dort mit gegenläufiger Marge-Kontrolle-Konstellation.",
    4: "In Touchpoint 5 werden alle Entscheidungen auf Konsistenz geprüft; in der Klausur ist dies Aufgabe 4 an einem Unternehmen mit anderem Geschäftsmodell, bei dem Kontrolle anders wiegt.",
    5: "In der Klausur ist dies Aufgabe 5, der grösste Block; der Fall wechselt, die Denkoperationen bleiben.",
}


def feedback_release_date(tp: int) -> date | None:
    """Das KI-Feedback an die Stammgruppen ist erst NACH dem Termin freigegeben
    (Leitplanke feedback_only_after_session): ab dem Tag nach dem Touchpoint."""
    schedule = BRIEFING_SCHEDULE.get(tp)
    if not schedule:
        return None
    return schedule["termin"] + timedelta(days=1)


def feedback_released(tp: int, today: date | None = None) -> bool:
    release = feedback_release_date(tp)
    if release is None:
        return False
    current = today or datetime.now(timezone.utc).date()
    return current >= release


class Criterion(BaseModel):
    name: str
    ueberzeugend: str
    tragfaehig: str
    ansatzweise: str


class Baustein(BaseModel):
    key: str                       # "baustein1" | "baustein2"
    slide: int                     # 2 | 3
    title: str
    exam_ref: str
    criteria: list[Criterion]
    typical_weaknesses: str = ""


class FormalChecks(BaseModel):
    slide2_max_chars: int
    slide3_max_chars: int
    chars_include_spaces: bool = True
    full_sentences_required: bool = True
    code_pattern: str
    filename_pattern: str
    submission_format: str = "pptx_3_slides_official_template"
    report_only_never_grade: bool = True


class ExampleSubmission(BaseModel):
    slide2: str
    slide3: str
    calibration_note: str


class BriefingRubric(BaseModel):
    tp: int
    version: str
    date: str
    course: str = "BWL A HS26"
    exam_ref: list[str] = Field(default_factory=list)
    learning_objectives: list[str] = Field(default_factory=list)
    case_document: str = "Case Study ON"
    case_chapter: str = ""
    case_references: str = ""
    guardrails: list[str] = Field(default_factory=list)
    formal_checks: FormalChecks
    bausteine: list[Baustein]
    levels: list[str] = Field(default_factory=lambda: ["ueberzeugend", "tragfaehig", "ansatzweise"])
    outputs: dict = Field(default_factory=dict)
    examples: dict[str, ExampleSubmission] = Field(default_factory=dict)

    def baustein(self, key: str) -> Baustein:
        for b in self.bausteine:
            if b.key == key:
                return b
        raise KeyError(key)

    def max_chars(self, baustein_key: str) -> int:
        slide = self.baustein(baustein_key).slide
        return self.formal_checks.slide2_max_chars if slide == 2 else self.formal_checks.slide3_max_chars

    @property
    def code_regex(self) -> re.Pattern[str]:
        return re.compile(self.formal_checks.code_pattern, re.IGNORECASE)

    @property
    def filename_regex(self) -> re.Pattern[str]:
        # Die Vorlage schreibt .pptx vor; DOCX/PDF werden als Abweichung
        # gemeldet, nicht abgewiesen (report_only_never_grade).
        return re.compile(self.formal_checks.filename_pattern, re.IGNORECASE)


def _rubric_path(tp: int) -> Path:
    return KI_RUBRICS_DIR / f"ki_rubrics_tp{tp}.json"


@lru_cache(maxsize=8)
def load_rubric(tp: int) -> BriefingRubric:
    """Lädt die Rubric eines Touchpoints; ValueError bei unbekanntem TP."""
    if tp not in SUPPORTED_TPS:
        raise ValueError(f"Ungültiger Touchpoint: {tp} (erlaubt: 1–5)")
    path = _rubric_path(tp)
    if not path.exists():
        raise ValueError(f"Rubric-Datei fehlt: {path.name}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    meta = payload.get("meta", {})
    case = meta.get("case", {}) or {}
    bausteine = [
        Baustein(
            key=key,
            slide=int(data.get("slide", 2 if key.endswith("1") else 3)),
            title=str(data.get("title", key)),
            exam_ref=str(data.get("exam_ref", "")),
            criteria=[Criterion(**c) for c in data.get("criteria", [])],
            typical_weaknesses=str(data.get("typical_weaknesses", "")),
        )
        for key, data in payload.get("rubrics", {}).items()
    ]
    examples = {
        level: ExampleSubmission(**data)
        for level, data in payload.get("example_submissions", {}).items()
        if isinstance(data, dict) and {"slide2", "slide3", "calibration_note"} <= set(data)
    }
    return BriefingRubric(
        tp=int(meta.get("touchpoint", tp)),
        version=str(meta.get("version", "")),
        date=str(meta.get("date", "")),
        course=str(meta.get("course", "BWL A HS26")),
        exam_ref=list(meta.get("exam_ref", [])),
        learning_objectives=list(meta.get("learning_objectives", [])),
        case_document=str(case.get("document", "Case Study ON")),
        case_chapter=str(case.get("chapter", TP_CHAPTER.get(tp, "").upper())),
        case_references=str(case.get("references", "")),
        guardrails=list(payload.get("guardrails", [])),
        formal_checks=FormalChecks(**payload.get("formal_checks", {})),
        bausteine=bausteine,
        levels=list(payload.get("levels", [])) or ["ueberzeugend", "tragfaehig", "ansatzweise"],
        outputs=dict(payload.get("outputs", {})),
        examples=examples,
    )


@lru_cache(maxsize=8)
def load_case_chapter(letter: str) -> str:
    path = CASE_DIR / f"kapitel_{letter.lower()}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _extract_section(chapter_text: str, number: str) -> str:
    """Schneidet den Abschnitt ``## <number> …`` bis zur nächsten Überschrift aus."""
    match = re.search(rf"^## {re.escape(number)} .*$", chapter_text, re.MULTILINE)
    if not match:
        return ""
    rest = chapter_text[match.start():]
    nxt = re.search(r"^## ", rest[match.end() - match.start():], re.MULTILINE)
    return rest[: (match.end() - match.start()) + nxt.start()] if nxt else rest


@lru_cache(maxsize=8)
def case_context_for_tp(tp: int) -> str:
    """Case-Text für den Judge: das TP-Kapitel plus referenzierte Zusatzstellen."""
    letter = TP_CHAPTER.get(tp)
    if not letter:
        return ""
    parts = [load_case_chapter(letter).strip()]
    for extra_letter, number in TP_EXTRA_SECTIONS.get(tp, []):
        section = _extract_section(load_case_chapter(extra_letter), number).strip()
        if section:
            parts.append(f"(Referenzstelle aus Kapitel {extra_letter.upper()})\n\n{section}")
    return "\n\n".join(p for p in parts if p)


@lru_cache(maxsize=1)
def _template_texts() -> dict:
    path = KI_RUBRICS_DIR / "template_texts.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def template_boilerplate(tp: int) -> list[str]:
    """Textbausteine der offiziellen Abgabevorlage (Kenndaten-Labels,
    Auftragstexte, Umfangshinweise) — werden bei der Extraktion entfernt."""
    return list(_template_texts().get(str(tp), {}).get("boilerplate", []))


def template_slide_titles(tp: int) -> dict[int, str]:
    titles = _template_texts().get(str(tp), {}).get("slide_titles", {})
    return {int(k): v for k, v in titles.items()}
