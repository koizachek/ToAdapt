"""DOCX-Renderer für KI-Briefings.

Layout-Basis ist die Briefing-Vorlage der Kursleitung ("BWL A_Briefing
TPn.docx", HSG-Briefvorlage): ``backend/config/ki_rubrics/briefing_template.docx``
ist davon abgeleitet — Stile (Gill Sans MT Pro Light für Überschriften,
Palatino Linotype im Fliesstext, nummerierte Überschriften), Seitenränder und
die Fusszeile "Touchpoint n | BWL A HS2026 | Seite" bleiben, der Inhalt und
das schwere Titelbild wurden entfernt. Fehlt die Vorlage, fällt der Renderer
auf ein neutrales Dokument zurück.

Briefing (an die ÜGL): ein Dokument je Übungsgruppe mit einem
nummerierten Abschnitt je Stammgruppe — Kenndaten, formale Vorprüfung
(gemeldet, nicht bewertet), je Baustein Kernposition, tragende Argumente,
dünne Stellen mit Kriterienbezug als Rückfrage-Ansatz, die Einschätzung in
Prosa und der nächste Schritt; oben einmal der Ausblick des Touchpoints. Keine
Punkte, keine Stufen, keine interne Kriterien-Einstufung.

Sprache (seit 2026-09-28): Jeder Stammgruppen-Abschnitt steht in der Sprache
der Abgabe (``record["language"]``, Baustein-Titel aus der Rubric dieser
Sprache). Kopf, Einleitung und Ausblick sind deutsch, ausser alle Abschnitte
des Dokuments sind englisch. Feste Texte: ``backend/briefings/i18n.py``.
"""

from __future__ import annotations

import io
from datetime import date, datetime, timezone
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from backend.briefings.extraction import canvas_group
from backend.briefings.i18n import DOC_LABELS, FEED_FORWARD_EN, format_date_long, normalize_language, translate_note
from backend.briefings.rubrics import BRIEFING_SCHEDULE, FEED_FORWARD, KI_RUBRICS_DIR, BriefingRubric, load_rubric

TEMPLATE_PATH: Path = KI_RUBRICS_DIR / "briefing_template.docx"
_GREY = RGBColor(0x59, 0x59, 0x59)



def _fmt_date(value: date | None, language: str = "de") -> str:
    if not value:
        return "–"
    return value.strftime("%d/%m/%Y") if language == "en" else value.strftime("%d.%m.%Y")


def _new_document():
    return Document(str(TEMPLATE_PATH)) if TEMPLATE_PATH.exists() else Document()


def _style(doc, *candidates: str) -> str | None:
    names = {s.name for s in doc.styles}
    for name in candidates:
        if name in names:
            return name
    return None


def _para(doc, text: str, *, style: str | None = None, bold_label: str | None = None,
          italic: bool = False, size: float | None = None, grey: bool = False):
    p = doc.add_paragraph(style=style) if style else doc.add_paragraph()
    if bold_label:
        run = p.add_run(bold_label + " ")
        run.bold = True
        if size:
            run.font.size = Pt(size)
        if grey:
            run.font.color.rgb = _GREY
    run = p.add_run(text)
    run.italic = italic
    if size:
        run.font.size = Pt(size)
    if grey:
        run.font.color.rgb = _GREY
    return p


def _heading(doc, text: str, level: int) -> None:
    # Vorlage nutzt Heading 2/3 als nummerierte Gliederung (1, 1.1 …)
    doc.add_heading(text, level=level)


def _bullets(doc, items: list[str], empty_text: str) -> None:
    if not items:
        _para(doc, empty_text, italic=True)
        return
    style = _style(doc, "Aufzählung", "List Bullet")
    for item in items:
        doc.add_paragraph(str(item), style=style) if style else doc.add_paragraph(f"– {item}")


def _set_footer(doc, tp: int, language: str) -> None:
    """Fusszeile der Vorlage: erste Zelle trägt 'Touchpoint 1' → aktueller TP;
    bei englischem Kopf wird 'Seite' zu 'Page'."""
    page_de, page = DOC_LABELS["de"]["page"], DOC_LABELS[language]["page"]
    for section in doc.sections:
        for footer in (section.footer, section.first_page_footer, section.even_page_footer):
            try:
                tables = footer.tables
                paragraphs = list(footer.paragraphs)
            except Exception:
                continue
            for table in tables:
                for row in table.rows:
                    for cell in row.cells:
                        paragraphs.extend(cell.paragraphs)
            for p in paragraphs:
                for run in p.runs:
                    if run.text.strip().lower().startswith("touchpoint"):
                        run.text = f"Touchpoint {tp}"
                    elif language != "de" and page_de in run.text:
                        run.text = run.text.replace(page_de, page)


def _title_block(doc, *, kicker: str, title: str, subtitle: str, meta: str, language: str) -> None:
    """Titelblock im Stil der Vorlage: Kicker (Title), Titel (Subtitle),
    Untertitel + Kurs-/Case-Zeile (Normal), 'St.Gallen, <Datum>'."""
    _para(doc, kicker, style=_style(doc, "Title"))
    _para(doc, title, style=_style(doc, "Subtitle"))
    _para(doc, subtitle)
    _para(doc, meta, grey=True, size=9.5)
    today = datetime.now(timezone.utc).date()
    _para(
        doc,
        DOC_LABELS[language]["place_date"].format(date=format_date_long(today.day, today.month, today.year, language)),
        style=_style(doc, "Verfasser Ort Datum"),
    )


# ---------------------------------------------------------------------------
# KI-Briefing (ÜGL)
# ---------------------------------------------------------------------------

def _number(value: int, language: str) -> str:
    # Tausender: deutsch mit Apostroph (Schweiz), englisch mit Komma
    return f"{value:,}".replace(",", "'") if language == "de" else f"{value:,}"


def _formal_table(doc, formal: dict, rubric: BriefingRubric, language: str) -> None:
    L = DOC_LABELS[language]
    rows: list[tuple[str, str]] = []
    for key, n, slide in (("baustein1", 1, 2), ("baustein2", 2, 3)):
        chars = int(formal.get(f"{key}_chars", 0) or 0)
        limit = int(formal.get(f"{key}_max", rubric.max_chars(key)) or 0)
        status = L["within"] if chars <= limit else L["over"].format(n=chars - limit)
        rows.append((
            L["slide_row"].format(slide=slide, n=n),
            L["chars"].format(chars=_number(chars, language), limit=_number(limit, language), status=status),
        ))
    code = formal.get("code") or ""
    if code:
        parts = code.split("-")
        label = L["group_code"].format(tp=parts[0][2:], ueg=parts[1][3:], sg=parts[2][2:]) if len(parts) == 3 else code
        if not formal.get("code_matches_tp", True):
            label += L["tp_mismatch"]
    else:
        label = L["code_missing"]
    rows.append((L["row_group"], label))
    filename = str(formal.get("filename", ""))
    rows.append((L["row_filename"], filename))
    if canvas_group(filename):
        rows.append((L["row_canvas_group"], canvas_group(filename)))
    fmt = str(formal.get("format", "")).upper()
    rows.append((L["row_format"], fmt + (L["official_template"] if formal.get("template_detected") else "")))

    table = doc.add_table(rows=0, cols=2)
    table.style = _style(doc, "Table Grid") or table.style
    for label, value in rows:
        cells = table.add_row().cells
        cells[0].text = label
        cells[1].text = value
        for paragraph in cells[0].paragraphs + cells[1].paragraphs:
            for run in paragraph.runs:
                run.font.size = Pt(9)
    notes = [translate_note(str(n), language) for n in formal.get("notes", []) if str(n).strip()]
    if notes:
        _para(doc, " ".join(notes), italic=True, size=9)


def _record_language(record: dict) -> str:
    return normalize_language(record.get("language"))


def _rubric_for(rubric: BriefingRubric, language: str) -> BriefingRubric:
    """Rubric derselben Touchpoint-Version in der Sprache des Abschnitts."""
    if language == "de":
        return rubric
    try:
        return load_rubric(rubric.tp, language)
    except ValueError:  # pragma: no cover - englische Fassung fehlt → deutsche Titel
        return rubric


def _render_group(doc, record: dict, rubric: BriefingRubric) -> None:
    language = _record_language(record)
    L = DOC_LABELS[language]
    rubric = _rubric_for(rubric, language)
    sg = record.get("sg")
    code = record.get("code") or record.get("filename", "")
    title = L["group"].format(sg=sg) if sg else L["group_unassigned"]
    _heading(doc, f"{title} · {code}", 2)

    if record.get("status") == "extraction_failed":
        _para(doc, L["extraction_failed"] + translate_note(str(record.get("review_reason") or ""), language), italic=True)
        return

    if record.get("status") == "rejected":
        _para(doc, L["rejected"] + str(record.get("reject_reason") or ""), italic=True)
        return

    if record.get("injection_suspected"):
        p = _para(doc, L["injection"])
        for run in p.runs:
            run.bold = True
        for excerpt in record.get("injection_findings", []) or []:
            _para(doc, L["injection_found"].format(excerpt=translate_note(str(excerpt), language)), size=9, grey=True)

    if record.get("needs_human_review"):
        reason = translate_note(str(record.get("review_reason") or ""), language) or L["review_default"]
        _para(doc, L["review"].format(reason=reason), italic=True, size=9, grey=True)

    _heading(doc, L["formal_heading"], 3)
    _formal_table(doc, record.get("formal", {}) or {}, rubric, language)

    briefing = record.get("briefing", {}) or {}
    for b in rubric.bausteine:
        data = briefing.get(b.key, {}) or {}
        _heading(doc, L["baustein_heading"].format(n=b.key[-1], title=b.title, slide=b.slide, exam=b.exam_ref), 3)
        _para(doc, str(data.get("kernposition", "")), bold_label=L["kernposition"])
        _para(doc, "", bold_label=L["argumente"])
        _bullets(doc, list(data.get("tragende_argumente", []) or []), L["argumente_none"])
        _para(doc, "", bold_label=L["duenn"])
        _bullets(doc, list(data.get("duenne_stellen", []) or []), L["duenn_none"])
        _para(doc, str(data.get("einschaetzung", "")), bold_label=L["einschaetzung"])
        if data.get("naechster_schritt"):   # Alt-Datensätze vor 2026-09-28 ohne dieses Feld
            _para(doc, str(data["naechster_schritt"]), bold_label=L["naechster_schritt"])

    questions = briefing.get("rueckfragen", {}) or {}
    strengths = list(questions.get("zu_staerken", []) or [])
    weaknesses = list(questions.get("zu_schwaechen", []) or [])
    if strengths or weaknesses:
        _heading(doc, L["questions_heading"], 3)
        _para(doc, L["questions_intro"], italic=True, size=9, grey=True)
        _para(doc, "", bold_label=L["questions_strengths"])
        _bullets(doc, strengths, L["questions_none"])
        _para(doc, "", bold_label=L["questions_weaknesses"])
        _bullets(doc, weaknesses, L["questions_none"])


def document_language(records: list[dict]) -> str:
    """Kopfsprache: englisch nur, wenn ALLE Abschnitte englisch sind."""
    return "en" if records and all(_record_language(r) == "en" for r in records) else "de"


def render_briefing_docx(
    records: list[dict],
    *,
    rubric: BriefingRubric,
    ueg: str,
) -> bytes:
    """Rendert ein DOCX für eine Übungsgruppe (alle vorhandenen Stammgruppen)
    oder — bei genau einem Datensatz — für eine einzelne Stammgruppe.
    ``rubric`` ist die deutsche Rubric des Touchpoints; englische Abschnitte
    laden die englische Fassung selbst."""
    language = document_language(records)
    L = DOC_LABELS[language]
    head_rubric = _rubric_for(rubric, language)
    doc = _new_document()
    _set_footer(doc, rubric.tp, language)
    schedule = BRIEFING_SCHEDULE.get(rubric.tp, {})
    single = len(records) == 1
    bausteine = " · ".join(b.title for b in head_rubric.bausteine)

    title = L["title"].format(tp=rubric.tp, ueg=ueg or L["no_ueg"])
    if single and records[0].get("sg"):
        title += L["title_sg"].format(sg=records[0]["sg"])
    _title_block(
        doc,
        kicker=L["kicker"],
        title=title,
        subtitle=bausteine,
        meta=L["meta"].format(
            chapter=rubric.case_chapter,
            abgabe=_fmt_date(schedule.get("abgabe"), language),
            termin=_fmt_date(schedule.get("termin"), language),
            exam=", ".join(rubric.exam_ref),
            version=rubric.version,
            date=rubric.date,
        ),
        language=language,
    )

    _para(doc, L["intro"], italic=True, size=9.5)
    outlook = (FEED_FORWARD_EN if language == "en" else FEED_FORWARD).get(rubric.tp)
    if outlook:
        _para(doc, outlook, bold_label=L["outlook"], size=9.5)
    ordered = sorted(records, key=lambda r: (r.get("sg") is None, int(r.get("sg") or 99), str(r.get("filename", ""))))
    for record in ordered:
        _render_group(doc, record, rubric)

    footer = _para(doc, L["footer"], size=8, grey=True)
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
