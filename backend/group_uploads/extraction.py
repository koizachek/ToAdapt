"""ZIP-/PDF-Verarbeitung für hochgeladene Gruppenarbeiten.

Die Gruppen erstellen ihre Abgaben außerhalb der Plattform und liefern PDFs
mit einheitlichem Deckblatt (Gruppenindikator, z.B. "Gruppe 12"). Der
Master-Tutor lädt sie als ZIP hoch; hier passiert die reine, LLM-freie
Verarbeitung: ZIP entpacken (nur im Speicher, nie aufs Dateisystem),
PDF-Text extrahieren, Gruppencode vom Deckblatt parsen.

Alle Funktionen sind pur und ohne LLM direkt testbar.
"""

from __future__ import annotations

import io
import re
import zipfile

from pypdf import PdfReader

from backend.anonymize import normalize_group_code

# Harte Limits gegen ZIP-Bomben und Speicherfraß. ~80 Übungsgruppen pro
# Kurs; ein Batch pro Touchpoint bleibt deutlich darunter.
MAX_ZIP_ENTRIES = 200
MAX_PDF_BYTES = 25 * 1024 * 1024          # pro PDF (unkomprimiert)
MAX_TOTAL_BYTES = 300 * 1024 * 1024       # Summe aller Einträge (unkomprimiert)

# Dokumenttext wird für den Judge gedeckelt (Token-Kosten); der Anfang des
# Dokuments trägt bei den vorgegebenen Formaten (Memo, Decision Log,
# Strategy-on-a-Page) die Substanz.
MAX_TEXT_CHARS = 24000

# Deckblatt-Muster: "Gruppe 12", "Gruppe: G12", "Gruppennummer 7",
# "Gruppen-Nr.: 12", "Group 3", "Group number: 12".
_GROUP_PATTERNS = [
    re.compile(
        r"gruppe(?:n\s*-?\s*(?:nummer|nr\.?|code))?\s*[:#]?\s*([A-Za-z]?\s?\d{1,4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"group(?:\s*-?\s*(?:number|no\.?|code))?\s*[:#]?\s*([A-Za-z]?\s?\d{1,4})",
        re.IGNORECASE,
    ),
]


class ZipValidationError(ValueError):
    """Ungültiges oder zu großes ZIP — als 400 an den Aufrufer."""


def list_pdf_entries(zip_bytes: bytes) -> list[tuple[str, bytes]]:
    """Liefert (dateiname, pdf_bytes) für alle PDF-Einträge des ZIP.

    Ignoriert Verzeichnisse, macOS-Metadaten (__MACOSX, .DS_Store) und
    Nicht-PDFs. Wirft ZipValidationError bei kaputtem Archiv oder
    verletzten Limits — alles bleibt im Speicher, nichts wird entpackt
    geschrieben (kein Pfad-Traversal-Risiko).
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise ZipValidationError("Datei ist kein gültiges ZIP-Archiv.") from exc

    infos = [
        info for info in archive.infolist()
        if not info.is_dir()
        and not info.filename.startswith("__MACOSX/")
        and not info.filename.rsplit("/", 1)[-1].startswith(".")
    ]
    if len(infos) > MAX_ZIP_ENTRIES:
        raise ZipValidationError(
            f"ZIP enthält zu viele Dateien (max. {MAX_ZIP_ENTRIES})."
        )

    total = 0
    entries: list[tuple[str, bytes]] = []
    for info in infos:
        if not info.filename.lower().endswith(".pdf"):
            continue
        if info.file_size > MAX_PDF_BYTES:
            raise ZipValidationError(
                f"'{info.filename}' überschreitet das PDF-Limit von "
                f"{MAX_PDF_BYTES // (1024 * 1024)} MB."
            )
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise ZipValidationError("ZIP-Inhalt überschreitet das Gesamt-Limit.")
        entries.append((info.filename.rsplit("/", 1)[-1], archive.read(info)))

    if not entries:
        raise ZipValidationError("ZIP enthält keine PDF-Dateien.")
    return entries


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extrahiert den Text aller Seiten (gedeckelt auf MAX_TEXT_CHARS).

    Wirft ValueError, wenn das PDF nicht lesbar ist oder keinen Text
    enthält (z.B. reiner Scan ohne OCR).
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        parts: list[str] = []
        chars = 0
        for page in reader.pages:
            text = (page.extract_text() or "").strip()
            if text:
                parts.append(text)
                chars += len(text)
            if chars >= MAX_TEXT_CHARS:
                break
    except Exception as exc:
        raise ValueError("PDF konnte nicht gelesen werden.") from exc

    full = "\n\n".join(parts).strip()
    if not full:
        raise ValueError("PDF enthält keinen extrahierbaren Text (Scan ohne OCR?).")
    return full[:MAX_TEXT_CHARS]


def parse_group_code(document_text: str) -> str:
    """Liest den Gruppenindikator vom Deckblatt (Anfang des Dokuments).

    Sucht nur im vorderen Textbereich (Deckblatt), damit spätere Erwähnungen
    anderer Gruppen keinen Fehl-Match erzeugen. Rückgabe normalisiert
    ('12' → 'G12') oder '' wenn kein Indikator gefunden wurde — der
    Master-Tutor kann die Zuordnung dann manuell nachtragen.
    """
    cover = document_text[:1500]
    for pattern in _GROUP_PATTERNS:
        match = pattern.search(cover)
        if match:
            return normalize_group_code(match.group(1).replace(" ", ""))
    return ""
