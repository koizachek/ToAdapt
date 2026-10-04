"""Case-Study-DOCX → Kapiteldateien der Briefing-Pipeline.

Liest die Word-Fassung des Running Case ON (deutsch und englisch) und schreibt
die Markdown-Kapitel, die ``backend/briefings/rubrics.py`` (``load_case_chapter``,
``case_context_for_tp``) und ``backend/briefings/case_numbers.py`` lesen:

    backend/config/ki_rubrics/case/kapitel_0_einfuehrung.md … kapitel_e.md
    backend/config/ki_rubrics/case/en/kapitel_0_einfuehrung.md … kapitel_e.md

Format (vom Code vorausgesetzt):
- ``# 2 Kapitel A`` / ``## 2.1 Die Gründung`` — Kapitel und Abschnitte werden
  durchnummeriert (Einführung = 1, Kapitel A–E = 2–6); ``_extract_section``
  sucht ``^## 2.8 ``, die Rubrics verweisen auf «Abschnitt 2.8».
- ``Exhibit A5: Stakeholder-Übersicht`` als eigene Zeile, direkt gefolgt von
  den Tabellenzeilen ``| … | … |`` ohne Trennzeile — ``stakeholder_table``
  liest die Tabelle so.
- Textboxen («ON-Perspektive: …») stehen als Absätze an ihrer Stelle.
- Fussnoten: Verweis ``[^n]`` im Text, Wortlaut am Ende des Kapitels unter
  «Fussnoten» — Zahlen in Fussnoten zählen beim Zahlenabgleich als Fundstelle.
- Literatur- und Hilfsmittelverzeichnis landen in kapitel_0_einfuehrung.md
  (nie im Prompt eines Touchpoints, aber im Zahlenindex).

Quelle: ``internal/Unterlagen für AI-Pipeline/`` (gitignored). Aufruf (vom Repo-Root):
    .venv/bin/python scripts/convert_case_docx.py \\
        --de "internal/Unterlagen für AI-Pipeline/Case Study ON_DE.docx" \\
        --en "internal/Unterlagen für AI-Pipeline/Case_Study_ON_EN.docx"
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

from lxml import etree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"

CASE_DIR = Path(__file__).resolve().parent.parent / "backend" / "config" / "ki_rubrics" / "case"

# Kapitelüberschriften (Überschrift 2) → Zieldatei und Kapitelnummer.
CHAPTERS = {
    "de": {
        "Einführung": ("kapitel_0_einfuehrung.md", 1, "Einführung und Hinweise"),
        "Kapitel A": ("kapitel_a.md", 2, None), "Kapitel B": ("kapitel_b.md", 3, None),
        "Kapitel C": ("kapitel_c.md", 4, None), "Kapitel D": ("kapitel_d.md", 5, None),
        "Kapitel E": ("kapitel_e.md", 6, None),
        "Literaturverzeichnis": ("kapitel_0_einfuehrung.md", 7, None),
        "Hilfsmittelverzeichnis": ("kapitel_0_einfuehrung.md", 8, None),
    },
    "en": {
        "Introduction": ("kapitel_0_einfuehrung.md", 1, "Introduction and Notes"),
        "Chapter A": ("kapitel_a.md", 2, None), "Chapter B": ("kapitel_b.md", 3, None),
        "Chapter C": ("kapitel_c.md", 4, None), "Chapter D": ("kapitel_d.md", 5, None),
        "Chapter E": ("kapitel_e.md", 6, None),
        "References": ("kapitel_0_einfuehrung.md", 7, None),
        "List of Aids": ("kapitel_0_einfuehrung.md", 8, None),
    },
}
FOOTNOTES_HEADING = {"de": "Fussnoten", "en": "Footnotes"}
SKIP_STYLES = {"Verzeichnis1", "Verzeichnis2", "Verzeichnis3", "Abbildungsverzeichnis",
               "Inhaltsverzeichnisberschrift", "VerfasserOrtDatum", "Titel", "Untertitel"}
_CAPTION_SEQ_RE = re.compile(r"^\d+\s+(?=Exhibit\b)")


def _local(el: etree._Element) -> str:
    return etree.QName(el).localname


def _text_of(el: etree._Element, boxes: list[str] | None = None) -> str:
    """Text eines Absatzes in Dokumentreihenfolge. Textboxen (mc:Choice) werden
    in ``boxes`` gesammelt, die Word-Fallback-Kopie wird übersprungen."""
    parts: list[str] = []
    for child in el:
        tag = _local(child)
        ns = child.tag.split("}")[0] + "}"
        if ns == MC and tag == "Fallback":
            continue
        if tag == "txbxContent":
            if boxes is not None:
                box = "\n".join(p for p in (_text_of(p) for p in child.iter(W + "p")) if p.strip())
                if box.strip():
                    boxes.append(box)
            continue
        if tag == "t":
            parts.append(child.text or "")
        elif tag == "tab":
            parts.append(" ")
        elif tag == "br":
            parts.append("\n")
        elif tag == "footnoteReference":
            parts.append(f"[^{child.get(W + 'id')}]")
        elif tag == "footnoteRef":
            continue
        else:
            parts.append(_text_of(child, boxes))
    return "".join(parts)


def _style(p: etree._Element) -> str:
    st = p.find(f"{W}pPr/{W}pStyle")
    return st.get(W + "val") if st is not None else ""


def _table_rows(tbl: etree._Element) -> list[str]:
    rows: list[str] = []
    for tr in tbl.iter(W + "tr"):
        cells = []
        for tc in tr.findall(W + "tc"):
            cells.append(" ".join(_text_of(p).strip() for p in tc.findall(W + "p")).strip())
        rows.append("| " + " | ".join(cells) + " |")
    return rows


def _footnotes(z: zipfile.ZipFile) -> dict[str, str]:
    if "word/footnotes.xml" not in z.namelist():
        return {}
    root = etree.fromstring(z.read("word/footnotes.xml"))
    out: dict[str, str] = {}
    for note in root.findall(W + "footnote"):
        text = " ".join(_text_of(p).strip() for p in note.findall(W + "p")).strip()
        if text:
            out[note.get(W + "id")] = re.sub(r"\s+", " ", text)
    return out


def convert(path: Path, language: str) -> dict[str, list[str]]:
    """Gibt je Zieldatei die Zeilen zurück."""
    z = zipfile.ZipFile(path)
    body = etree.fromstring(z.read("word/document.xml")).find(W + "body")
    footnotes = _footnotes(z)
    chapters = CHAPTERS[language]
    files: dict[str, list[str]] = {}
    current: list[str] | None = None
    chapter_no = 0
    section_no = 0
    used_notes: list[str] = []

    def flush_footnotes() -> None:
        if current is None or not used_notes:
            return
        current.append(f"### {FOOTNOTES_HEADING[language]}")
        current.append("")
        for note_id in used_notes:
            current.append(f"[^{note_id}] {footnotes.get(note_id, '')}")
        current.append("")
        used_notes.clear()

    def note_refs(text: str) -> None:
        for note_id in re.findall(r"\[\^(\d+)\]", text):
            if note_id not in used_notes:
                used_notes.append(note_id)

    for el in body:
        tag = _local(el)
        if tag == "p":
            style = _style(el)
            boxes: list[str] = []
            text = _text_of(el, boxes).strip()
            if style == "berschrift2":
                flush_footnotes()
                if text not in chapters:
                    print(f"WARNUNG: unbekannte Kapitelüberschrift «{text}» — übersprungen", file=sys.stderr)
                    current = None
                    continue
                filename, chapter_no, title = chapters[text]
                section_no = 0
                current = files.setdefault(filename, [])
                if current:
                    current.append("")
                current.append(f"# {chapter_no} {title or text}")
                current.append("")
                continue
            if current is None or style in SKIP_STYLES:
                continue
            if style == "berschrift3":
                section_no += 1
                current.append(f"## {chapter_no}.{section_no} {text}")
                current.append("")
                continue
            if style == "Beschriftung":
                caption = _CAPTION_SEQ_RE.sub("", text)
                if caption.startswith("Exhibit"):
                    current.append(caption)      # Tabelle folgt direkt, ohne Leerzeile
                    continue
                text = caption
            if text:
                note_refs(text)
                current.append(text)
                current.append("")
            for box in boxes:
                note_refs(box)
                current.append(re.sub(r"\n+", " ", box).strip())
                current.append("")
        elif tag == "tbl":
            if current is None:
                continue
            rows = _table_rows(el)
            for row in rows:
                note_refs(row)
            current.extend(rows)
            current.append("")
    flush_footnotes()
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--de", type=Path, help="deutsche Case-Study-DOCX")
    parser.add_argument("--en", type=Path, help="englische Case-Study-DOCX")
    parser.add_argument("--dry-run", action="store_true", help="nur Gliederung zeigen, nichts schreiben")
    args = parser.parse_args()
    if not args.de and not args.en:
        parser.error("--de und/oder --en angeben")
    for language, path in (("de", args.de), ("en", args.en)):
        if not path:
            continue
        files = convert(path, language)
        target = CASE_DIR / "en" if language == "en" else CASE_DIR
        for filename, lines in files.items():
            content = "\n".join(lines).rstrip() + "\n"
            headings = [ln for ln in lines if ln.startswith("#") or ln.startswith("Exhibit")]
            print(f"[{language}] {filename}: {len(content)} Zeichen, {len(headings)} Überschriften/Exhibits")
            if args.dry_run:
                for h in headings:
                    print("   ", h)
                continue
            (target / filename).write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
