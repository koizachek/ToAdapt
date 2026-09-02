"""DOCX-Renderer für KI-Briefings (Download durch die ÜGL).

Ein Dokument je Übungsgruppe und Touchpoint mit einem Abschnitt je
Stammgruppe (SG1 … SG8) — oder ein Einzeldokument je Stammgruppe. Enthält
ausschliesslich tutor-sichtbare Inhalte: Kenndaten, formale Vorprüfung
(gemeldet, nicht bewertet), je Baustein Kernposition, tragende Argumente,
dünne Stellen als Rückfrage-Ansatz und die Einschätzung in Prosa. Keine
Punkte, keine Stufen, keine interne Kriterien-Einstufung.
"""

from __future__ import annotations

import io
from datetime import date

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from backend.briefings.rubrics import BRIEFING_SCHEDULE, BriefingRubric

_GREY = RGBColor(0x59, 0x59, 0x59)


def _fmt_date(value: date | None) -> str:
    return value.strftime("%d.%m.%Y") if value else "–"


def _heading(doc: Document, text: str, level: int) -> None:
    doc.add_heading(text, level=level)


def _para(doc: Document, text: str, *, bold_label: str | None = None, italic: bool = False, size: int | None = None):
    p = doc.add_paragraph()
    if bold_label:
        run = p.add_run(bold_label + " ")
        run.bold = True
        if size:
            run.font.size = Pt(size)
    run = p.add_run(text)
    run.italic = italic
    if size:
        run.font.size = Pt(size)
    return p


def _bullets(doc: Document, items: list[str], empty_text: str) -> None:
    if not items:
        _para(doc, empty_text, italic=True)
        return
    for item in items:
        doc.add_paragraph(str(item), style="List Bullet")


def _formal_table(doc: Document, formal: dict, rubric: BriefingRubric) -> None:
    rows: list[tuple[str, str]] = []
    for key, label in (("baustein1", "Folie 2 (Baustein 1)"), ("baustein2", "Folie 3 (Baustein 2)")):
        chars = int(formal.get(f"{key}_chars", 0) or 0)
        limit = int(formal.get(f"{key}_max", rubric.max_chars(key)) or 0)
        status = "innerhalb der Grenze" if chars <= limit else f"über der Grenze (+{chars - limit})"
        rows.append((label, f"{chars:,} von {limit:,} Zeichen · {status}".replace(",", "'")))
    code = formal.get("code") or "nicht erkennbar"
    code_note = "gültig" if formal.get("code_valid") else "nicht im vorgegebenen Format"
    if formal.get("code") and not formal.get("code_matches_tp", True):
        code_note += ", Touchpoint im Code weicht ab"
    rows.append(("Code", f"{code} · {code_note}"))
    rows.append((
        "Dateiname",
        f"{formal.get('filename', '')} · "
        + ("entspricht dem Muster" if formal.get("filename_valid") else "weicht vom Muster ab"),
    ))
    fmt = str(formal.get("format", "")).upper()
    rows.append((
        "Format",
        fmt + (" · offizielle Vorlage erkannt" if formal.get("template_detected") else " · Vorlage nicht erkannt"),
    ))
    if formal.get("members_filled") is not None:
        rows.append(("Mitglieder", "ausgefüllt" if formal.get("members_filled") else "nicht ausgefüllt"))
    if formal.get("full_sentences_hint"):
        rows.append(("Satzform", str(formal["full_sentences_hint"])))

    table = doc.add_table(rows=0, cols=2)
    table.style = "Light Grid Accent 1" if "Light Grid Accent 1" in [s.name for s in doc.styles] else "Table Grid"
    for label, value in rows:
        cells = table.add_row().cells
        cells[0].text = label
        cells[1].text = value
        for paragraph in cells[0].paragraphs + cells[1].paragraphs:
            for run in paragraph.runs:
                run.font.size = Pt(9)
    notes = [str(n) for n in formal.get("notes", []) if str(n).strip()]
    if notes:
        _para(doc, " ".join(notes), italic=True, size=9)


def _render_group(doc: Document, record: dict, rubric: BriefingRubric) -> None:
    sg = record.get("sg")
    code = record.get("code") or record.get("filename", "")
    title = f"Stammgruppe SG{sg}" if sg else "Stammgruppe (nicht zugeordnet)"
    _heading(doc, f"{title} · {code}", 1)

    if record.get("status") == "extraction_failed":
        _para(
            doc,
            "Die Datei konnte nicht gelesen werden — bitte die Abgabe direkt öffnen. "
            + str(record.get("review_reason") or ""),
            italic=True,
        )
        return

    if record.get("needs_human_review"):
        reason = record.get("review_reason") or "Automatische Verdichtung mit Vorbehalt."
        p = _para(doc, f"Hinweis: {reason}", italic=True, size=9)
        for run in p.runs:
            run.font.color.rgb = _GREY

    _heading(doc, "Formale Vorprüfung (gemeldet, nicht bewertet)", 2)
    _formal_table(doc, record.get("formal", {}) or {}, rubric)

    briefing = record.get("briefing", {}) or {}
    for b in rubric.bausteine:
        data = briefing.get(b.key, {}) or {}
        _heading(doc, f"Baustein {b.key[-1]} · {b.title} (Folie {b.slide}, Klausur {b.exam_ref})", 2)
        _para(doc, str(data.get("kernposition", "")), bold_label="Kernposition:")
        _para(doc, "", bold_label="Tragende Argumente:")
        _bullets(doc, list(data.get("tragende_argumente", []) or []), "Keine tragenden Argumente identifiziert.")
        _para(doc, "", bold_label="Dünne Stellen (Ansatz für Rückfragen):")
        _bullets(doc, list(data.get("duenne_stellen", []) or []), "Keine dünnen Stellen identifiziert.")
        _para(doc, str(data.get("einschaetzung", "")), bold_label="Einschätzung:")


def render_briefing_docx(
    records: list[dict],
    *,
    rubric: BriefingRubric,
    ueg: str,
    missing_groups: list[int] | None = None,
) -> bytes:
    """Rendert ein DOCX für eine Übungsgruppe (alle vorhandenen Stammgruppen)
    oder — bei genau einem Datensatz — für eine einzelne Stammgruppe."""
    doc = Document()
    styles = doc.styles
    styles["Normal"].font.name = "Calibri"
    styles["Normal"].font.size = Pt(10.5)

    schedule = BRIEFING_SCHEDULE.get(rubric.tp, {})
    single = len(records) == 1
    heading = f"KI-Briefing Touchpoint {rubric.tp} · Übungsgruppe {ueg or 'ohne Zuordnung'}"
    if single and records[0].get("sg"):
        heading += f" · Stammgruppe SG{records[0]['sg']}"
    doc.add_heading(heading, level=0)

    sub = doc.add_paragraph()
    run = sub.add_run(
        f"{rubric.course} · Running Case ON, Kapitel {rubric.case_chapter} · "
        f"Abgabe {_fmt_date(schedule.get('abgabe'))} · Termin {_fmt_date(schedule.get('termin'))} · "
        f"Klausurbezug {', '.join(rubric.exam_ref)} · Rubric {rubric.version} vom {rubric.date}"
    )
    run.font.size = Pt(9)
    run.font.color.rgb = _GREY

    intro = doc.add_paragraph()
    intro_run = intro.add_run(
        "Nur für die Übungsgruppenleitung. Dieses Briefing verdichtet jede Abgabe entlang der "
        "Bausteine des Arbeitsauftrags: Kernposition, tragende Argumente, dünne Stellen. Es enthält "
        "keine Punkte, keine Stufen und keine Musterlösung — jede Wahl ist zulässig, beurteilt wird "
        "nur, ob die Begründung trägt. Die Wahl der Spannungslinie und der Rückfragen bleibt Ihre "
        "didaktische Entscheidung. Das Feedback an die Stammgruppen entsteht erst nach dem Termin."
    )
    intro_run.font.size = Pt(9.5)
    intro_run.italic = True

    if missing_groups:
        p = doc.add_paragraph()
        r = p.add_run("Keine Abgabe eingegangen: " + ", ".join(f"SG{n}" for n in missing_groups))
        r.font.size = Pt(9.5)
        r.bold = True

    ordered = sorted(records, key=lambda r: (r.get("sg") is None, int(r.get("sg") or 99), str(r.get("filename", ""))))
    for record in ordered:
        _render_group(doc, record, rubric)

    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    fr = footer.add_run("Automatisch erstellt durch ToAdapt · KI-Pipeline BWL A HS26")
    fr.font.size = Pt(8)
    fr.font.color.rgb = _GREY

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Produkt 2: KI-Feedback an die Stammgruppe (ein Dokument je Stammgruppe)
# ---------------------------------------------------------------------------

def render_feedback_docx(record: dict, *, rubric: BriefingRubric) -> bytes:
    """Rückmeldung an EINE Stammgruppe: je Baustein was trägt / was bleibt dünn /
    nächster Schritt, Abschluss Feed-forward. Keine Punkte, keine Stufen, keine
    formale Vorprüfung, keine interne Einstufung — nur die Rückmeldung selbst."""
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)

    schedule = BRIEFING_SCHEDULE.get(rubric.tp, {})
    sg = record.get("sg")
    code = record.get("code") or record.get("filename", "")
    title = f"Rückmeldung Touchpoint {rubric.tp}"
    if sg:
        title += f" · Stammgruppe SG{sg}"
    doc.add_heading(title, level=0)

    sub = doc.add_paragraph()
    run = sub.add_run(
        f"{rubric.course} · Running Case ON, Kapitel {rubric.case_chapter} · Abgabe {code} · "
        f"Termin {_fmt_date(schedule.get('termin'))} · Klausurbezug {', '.join(rubric.exam_ref)}"
    )
    run.font.size = Pt(9)
    run.font.color.rgb = _GREY

    intro = doc.add_paragraph()
    intro_run = intro.add_run(
        "Diese Rückmeldung bezieht sich ausschliesslich auf Ihr eigenes Ergebnis und folgt denselben "
        "Kriterien, die im Bewertungsraster der Klausur für die entsprechende Teilaufgabe gelten. Sie "
        "enthält keine Punkte und keine Musterlösung: Jede Wahl ist zulässig; es geht nur darum, wo "
        "Ihre Begründung trägt und wo sie dünn bleibt."
    )
    intro_run.font.size = Pt(9.5)
    intro_run.italic = True

    feedback = record.get("feedback", {}) or {}
    for b in rubric.bausteine:
        data = feedback.get(b.key, {}) or {}
        _heading(doc, f"Baustein {b.key[-1]} · {b.title} (Folie {b.slide}, Klausur {b.exam_ref})", 1)
        _para(doc, str(data.get("was_traegt", "")), bold_label="Was trägt:")
        _para(doc, str(data.get("was_bleibt_duenn", "")), bold_label="Was bleibt dünn:")
        _para(doc, str(data.get("naechster_schritt", "")), bold_label="Nächster Schritt:")

    _heading(doc, "Ausblick", 1)
    _para(doc, str(feedback.get("feed_forward", "")))

    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    fr = footer.add_run("Automatisch erstellt durch ToAdapt · KI-Pipeline BWL A HS26 · weitergegeben durch Ihre Übungsgruppenleitung")
    fr.font.size = Pt(8)
    fr.font.color.rgb = _GREY

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
