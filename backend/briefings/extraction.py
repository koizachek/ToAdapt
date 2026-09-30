"""Extraktion der Stammgruppen-Abgaben (PPTX, DOCX, PDF) aus dem Master-ZIP.

Alles läuft rein im Speicher (nichts wird entpackt auf Platte geschrieben),
ohne LLM und ist pur testbar. Ergebnis je Datei ist ein
``ExtractedSubmission`` mit:

- Kenndaten (Touchpoint, Übungsgruppe UEGxx, Stammgruppe SGy, Code) — aus
  den benannten Kenndaten-Shapes der offiziellen Vorlage (``KENN_*``),
  ersatzweise per Regex aus dem Text, ersatzweise aus dem Dateinamen.
- Text je Baustein (Folie 2 = Baustein 1, Folie 3 = Baustein 2), bereinigt
  um Vorlagentext (Titel, Auftragstext, Umfangshinweis, Platzhalter).
- Zeichenzahl je Baustein (inklusive Leerzeichen, ohne Absatzmarken —
  wie PowerPoint/Word zählen).

Die Mitgliedernamen auf dem Deckblatt (``KENN_NAMEN``) werden NIE
übernommen — nur ob das Feld ausgefüllt ist (formale Vorprüfung).
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterator

from pypdf import PdfReader

from backend.briefings.rubrics import SUPPORTED_TPS, load_rubric, template_boilerplate

SUPPORTED_EXTENSIONS = (".pptx", ".docx", ".pdf")

# Limits gegen ZIP-Bomben und Speicherfrass. Ein Semester-Upload umfasst bis
# zu 55 Übungsgruppen × 8 Stammgruppen = 440 Dateien je Touchpoint; die
# Vorlage wiegt ~0,7 MB (Bilder), daher grosszügige Einzel-/Gesamtlimits.
MAX_ZIP_ENTRIES = 600
MAX_FILE_BYTES = 40 * 1024 * 1024
MAX_TOTAL_BYTES = 1200 * 1024 * 1024

# Deckel für den Judge-Input je Baustein (die Vorlage erlaubt max. 1'650
# Zeichen; deutlich mehr deutet auf Fehlextraktion oder Regelverstoss hin).
MAX_BAUSTEIN_CHARS = 8000

CODE_RE = re.compile(
    r"TP\s*([1-5])\s*[-_– ]\s*UEG\s*(\d{1,2})\s*[-_– ]\s*SG\s*([1-8])\b",
    re.IGNORECASE,
)
FILENAME_RE = re.compile(
    r"TP\s*([1-5])[-_ ]UEG\s*(\d{1,2})[-_ ]SG\s*([1-8])",
    re.IGNORECASE,
)
# Code mit erkennbarem Touchpoint und Übungsgruppe, aber abweichender
# Stammgruppen-Schreibweise ("TP1-UEG06-SGA4", "TP1_UEG06_Team B2"): TP und
# UEG werden trotzdem übernommen, die Stammgruppe bleibt offen.
PARTIAL_CODE_RE = re.compile(r"TP\s*([1-5])\s*[-_– ]\s*UEG\s*(\d{1,2})(?!\d)", re.IGNORECASE)
_FILENAME_TP_RE = re.compile(r"(?<![A-Za-z])(?:TP|Touchpoint)[\s_+-]*([1-5])(?!\d)", re.IGNORECASE)
# Canvas-Export: "<gruppenname>_[LATE_]<id>_<abgabe-id>_<originalname>"
_CANVAS_PREFIX_RE = re.compile(r"^([^_]+)_(?:LATE_)?\d+_\d+_")
_BAUSTEIN_MARK = {
    1: re.compile(r"^\s*(?:folie\s*2\s*[-–:·]?\s*)?baustein\s*1\b", re.IGNORECASE),
    2: re.compile(r"^\s*(?:folie\s*3\s*[-–:·]?\s*)?baustein\s*2\b", re.IGNORECASE),
}
_PLACEHOLDER_PREFIXES = ("[ihre darstellung", "[ bitte ausfüllen", "[bitte ausfüllen")
_EMPTY_FIELD = {"", "__", "_", "[ bitte ausfüllen ]", "[bitte ausfüllen]"}


class ZipValidationError(ValueError):
    """Ungültiges oder zu grosses ZIP — als 400 an den Aufrufer."""


@dataclass
class Kenndaten:
    tp: int | None = None
    ueg: str = ""            # "UEG07"
    sg: int | None = None    # 1–8
    code: str = ""           # "TP1-UEG07-SG3"
    source: str = ""         # "kenndaten" | "text" | "filename" | ""


@dataclass
class ExtractedSubmission:
    filename: str
    format: str                       # "pptx" | "docx" | "pdf"
    kenndaten: Kenndaten
    baustein1: str = ""
    baustein2: str = ""
    baustein1_chars: int = 0
    baustein2_chars: int = 0
    slide_count: int | None = None
    template_detected: bool = False
    notes: list[str] = field(default_factory=list)
    # Versteckter Text in PPTX (weiss, winzig, ausserhalb der Folie) — wird
    # NICHT in die Bausteine übernommen, sondern nur gemeldet (Prompt-Injection).
    hidden_text: list[dict] = field(default_factory=list)
    # Labels entfernter personenbezogener Angaben (E-Mail, Matrikel, Namenszeile).
    pii_hits: list[str] = field(default_factory=list)
    # Grosse Bilder auf den Baustein-Folien (PPTX) — Text in Bildern wird nicht gelesen.
    picture_count: int = 0
    pictures_baustein1: int = 0
    pictures_baustein2: int = 0

    @property
    def has_content(self) -> bool:
        return bool(self.baustein1.strip() or self.baustein2.strip())


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def normalize_ueg(value: str | int | None) -> str:
    """'7' / '07' / 'UEG07' / 'ueg 7' → 'UEG07'; '' wenn nicht erkennbar."""
    if value is None:
        return ""
    match = re.fullmatch(r"\s*(?:UEG)?\s*0*(\d{1,2})\s*", str(value), re.IGNORECASE)
    if not match:
        return ""
    return f"UEG{int(match.group(1)):02d}"


def parse_uegs(value: str | None) -> list[str]:
    """Alle Übungsgruppen einer Tutor-Kennung: 'UEG07' → ['UEG07'];
    'UEG07+UEG12' / 'UEG07, UEG12' / '7 12' → ['UEG07', 'UEG12'].
    Eine ÜGL kann mehrere Übungsgruppen führen — die Kennung (Schlüssel in
    TEACHER_ACCESS_CODES) trägt sie alle. Nicht parsebare Teile werden ignoriert."""
    out: list[str] = []
    for token in re.split(r"[^A-Za-z0-9]+", str(value or "")):
        ueg = normalize_ueg(token)
        if ueg and ueg not in out:
            out.append(ueg)
    return out


def build_code(tp: int, ueg: str, sg: int) -> str:
    return f"TP{tp}-{ueg}-SG{sg}"


def _norm(text: str) -> str:
    text = text.replace("\x0b", " ").replace("·", "-").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip().lower()


def count_chars(text: str) -> int:
    """Zeichen inklusive Leerzeichen, ohne Zeilen-/Absatzumbrüche."""
    return len(text.replace("\r", "").replace("\n", "").replace("\x0b", ""))


_FORMAT_HINT_RE = re.compile(
    r"(format|dateiname|beispiel|z\.?\s?b\.?|analog zum code)\s*[:：]?\s*"
    r"TP\s*[1-5]\s*[-_– ]\s*UEG\s*\d{1,2}\s*[-_– ]\s*SG\s*[1-8](\.\w+)?",
    re.IGNORECASE,
)


def _without_format_hints(text: str) -> str:
    """Entfernt Beispiel-Codes aus Vorlagentexten ("Format:  TP1-UEG07-SG3",
    "Dateiname: TP1_UEG07_SG3.pptx"), damit eine unausgefüllte Vorlage nicht
    der Beispielgruppe zugeordnet wird."""
    return _FORMAT_HINT_RE.sub(" ", text or "")


def parse_code(text: str) -> tuple[int, str, int] | None:
    match = CODE_RE.search(_without_format_hints(text))
    if not match:
        return None
    return int(match.group(1)), normalize_ueg(match.group(2)), int(match.group(3))


def parse_code_from_filename(filename: str) -> tuple[int, str, int] | None:
    match = FILENAME_RE.search(filename or "")
    if not match:
        return None
    return int(match.group(1)), normalize_ueg(match.group(2)), int(match.group(3))


def parse_partial_code(text: str) -> tuple[int, str] | None:
    """Touchpoint und Übungsgruppe aus einem Code, dessen Stammgruppe nicht
    dem Muster SG1–SG8 folgt."""
    match = PARTIAL_CODE_RE.search(_without_format_hints(text))
    if not match:
        return None
    return int(match.group(1)), normalize_ueg(match.group(2))


def canvas_group(filename: str) -> str:
    """Gruppenname, den Canvas dem Dateinamen voranstellt ('stammteam3',
    'a4'); leer, wenn der Dateiname nicht aus einem Canvas-Export stammt."""
    match = _CANVAS_PREFIX_RE.match(filename or "")
    return match.group(1) if match else ""


def _original_name(filename: str) -> str:
    """Dateiname ohne Canvas-Präfix (Gruppenname und IDs)."""
    return _CANVAS_PREFIX_RE.sub("", filename or "")


def _merge_kenndaten(kd: Kenndaten, source: str, tp: int | None = None, ueg: str = "", sg: int | None = None) -> None:
    """Füllt nur, was noch fehlt; die erste Quelle, die etwas beiträgt, wird vermerkt."""
    changed = False
    if tp in SUPPORTED_TPS and not kd.tp:
        kd.tp, changed = tp, True
    if ueg and not kd.ueg:
        kd.ueg, changed = ueg, True
    if sg and not kd.sg:
        kd.sg, changed = sg, True
    if changed and not kd.source:
        kd.source = source


def _merge_from_text(kd: Kenndaten, source: str, text: str) -> None:
    parsed = parse_code(text)
    if parsed:
        _merge_kenndaten(kd, source, *parsed)
        return
    partial = parse_partial_code(text)
    if partial:
        _merge_kenndaten(kd, source, *partial)


def _merge_from_filename(kd: Kenndaten, filename: str) -> None:
    parsed = parse_code_from_filename(filename)
    if parsed:
        _merge_kenndaten(kd, "filename", *parsed)
        return
    # Sonst nur der Touchpoint ("…_TP1_…", "Touchpoint 1"): Die Übungsgruppe im
    # Dateinamen ist zu oft falsch — sie kommt vom Deckblatt oder aus den
    # übrigen Abgaben desselben Uploads.
    tp = _FILENAME_TP_RE.search(_original_name(filename))
    if tp:
        _merge_kenndaten(kd, "filename", tp=int(tp.group(1)))


def split_bausteine(text: str) -> tuple[str, str, bool]:
    """Teilt Fliesstext an 'Baustein 1' / 'Baustein 2'-Markern.

    Rückgabe (baustein1, baustein2, gefunden). Ohne Marker landet alles in
    Baustein 1 und ``gefunden`` ist False.
    """
    lines = (text or "").splitlines()
    idx = {1: None, 2: None}
    for i, line in enumerate(lines):
        for key, pattern in _BAUSTEIN_MARK.items():
            if idx[key] is None and pattern.match(line):
                idx[key] = i
    if idx[1] is None and idx[2] is None:
        return text.strip(), "", False
    start1 = (idx[1] + 1) if idx[1] is not None else 0
    if idx[2] is None:
        return "\n".join(lines[start1:]).strip(), "", True
    if idx[1] is None or idx[2] < idx[1]:
        return "", "\n".join(lines[idx[2] + 1:]).strip(), True
    b1 = "\n".join(lines[start1: idx[2]]).strip()
    b2 = "\n".join(lines[idx[2] + 1:]).strip()
    return b1, b2, True


def _strip_boilerplate_lines(text: str, boilerplate: set[str]) -> str:
    kept = []
    for line in (text or "").splitlines():
        n = _norm(line)
        if not n:
            continue
        if n in boilerplate or n.startswith(_PLACEHOLDER_PREFIXES):
            continue
        if re.fullmatch(r"\d{1,2}", n):          # Foliennummer
            continue
        if re.match(r"^max\.?\s*\d", n):          # Umfangshinweis
            continue
        kept.append(line.rstrip())
    return "\n".join(kept).strip()


def _boilerplate_set(tp: int | None) -> set[str]:
    tps = [tp] if tp in SUPPORTED_TPS else list(SUPPORTED_TPS)
    out: set[str] = set()
    for t in tps:
        out.update(_norm(s) for s in template_boilerplate(t))
    return out


# ---------------------------------------------------------------------------
# ZIP
# ---------------------------------------------------------------------------

def iter_submission_entries(zip_bytes: bytes) -> Iterator[tuple[str, bytes]]:
    """Liefert (dateiname, bytes) für alle PPTX/DOCX/PDF-Einträge, lazy.

    Verzeichnisse, macOS-Metadaten und andere Formate werden übersprungen.
    Wirft ZipValidationError bei kaputtem Archiv oder verletzten Limits.
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
        raise ZipValidationError(f"ZIP enthält zu viele Dateien (max. {MAX_ZIP_ENTRIES}).")

    selected = [i for i in infos if i.filename.lower().endswith(SUPPORTED_EXTENSIONS)]
    if not selected:
        raise ZipValidationError("ZIP enthält keine PPTX-, DOCX- oder PDF-Dateien.")

    total = 0
    for info in selected:
        if info.file_size > MAX_FILE_BYTES:
            raise ZipValidationError(
                f"'{info.filename}' überschreitet das Dateilimit von "
                f"{MAX_FILE_BYTES // (1024 * 1024)} MB."
            )
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise ZipValidationError("ZIP-Inhalt überschreitet das Gesamt-Limit.")

    for info in selected:
        yield _zip_entry_name(info).rsplit("/", 1)[-1], archive.read(info)


def _zip_entry_name(info: zipfile.ZipInfo) -> str:
    """zipfile liest Namen ohne UTF-8-Flag als CP437 — Umlaute und
    Gedankenstriche aus macOS/Canvas-Archiven kämen sonst verstümmelt an."""
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode("cp437").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


# ---------------------------------------------------------------------------
# PPTX
# ---------------------------------------------------------------------------

def _shape_texts(shape) -> list[tuple[str, str]]:
    """(shape_name, text) rekursiv über Gruppen und Tabellen."""
    out: list[tuple[str, str]] = []
    if getattr(shape, "shape_type", None) == 6 and hasattr(shape, "shapes"):  # GROUP
        for sub in shape.shapes:
            out.extend(_shape_texts(sub))
        return out
    if getattr(shape, "has_table", False) and shape.has_table:
        for row in shape.table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    out.append((shape.name, cell.text))
        return out
    if getattr(shape, "has_text_frame", False) and shape.has_text_frame:
        text = shape.text_frame.text
        if text.strip():
            out.append((shape.name, text))
    return out


# Ab diesem Anteil an der Folienfläche gilt ein Bild als Träger von Inhalt
# (Screenshot einer gestalteten Folie); kleinere sind Icons oder Logos.
LARGE_PICTURE_SHARE = 0.15


def _picture_count(shapes, slide_area: int, max_area: int | None = None) -> int:
    """Grosse Bilder auf einer Folie, rekursiv über Gruppen (PICTURE oder
    gefüllter Bildplatzhalter). In Gruppen zählt höchstens die Gruppenfläche."""
    count = 0
    for shape in shapes:
        area = (shape.width or 0) * (shape.height or 0)
        if max_area is not None:
            area = min(area, max_area)
        if getattr(shape, "shape_type", None) == 6 and hasattr(shape, "shapes"):
            count += _picture_count(shape.shapes, slide_area, area)
        elif getattr(shape, "shape_type", None) == 13 or type(shape).__name__ == "PlaceholderPicture":
            count += int(bool(slide_area) and area / slide_area >= LARGE_PICTURE_SHARE)
    return count


# Vorlagentitel der Baustein-Folien ("Baustein 1 - …", "Building block 2 - …")
_TEMPLATE_TITLE_RE = re.compile(r"^\s*(?:baustein|building\s+block)\s*[12]\b", re.IGNORECASE)


def _is_title(shape) -> bool:
    return bool(getattr(shape, "is_placeholder", False)) and shape.placeholder_format.type in (1, 3)


@lru_cache(maxsize=None)
def _baustein_titles() -> tuple[str, ...]:
    """Bausteintitel aller Touchpoints (deutsch und englisch), längste zuerst."""
    titles: set[str] = set()
    for tp in SUPPORTED_TPS:
        for language in ("de", "en"):
            try:
                titles.update(b.title.strip().lower() for b in load_rubric(tp, language).bausteine)
            except ValueError:
                continue
    return tuple(sorted((t for t in titles if t), key=len, reverse=True))


def _own_title_lines(text: str, boilerplate: set[str]) -> str:
    """Titelfeld einer Baustein-Folie: Der Vorlagentitel fällt weg ("Baustein 1
    - …", auch ohne Nummer), eine eigene Überschrift der Gruppe gehört zur Antwort."""
    lines: list[str] = []
    for line in text.splitlines():
        if _TEMPLATE_TITLE_RE.match(line):
            continue
        rest = line.strip()
        for title in _baustein_titles():
            if rest.lower().startswith(title):
                rest = rest[len(title):].lstrip(" -–—:·")
                break
        if rest:
            lines.append(rest)
    return _strip_boilerplate_lines("\n".join(lines), boilerplate)


def _is_pptx_boilerplate(shape, text: str, boilerplate: set[str]) -> bool:
    name = (getattr(shape, "name", "") or "").upper()
    if name.startswith("KOPF_") or name.startswith("L_") or name.startswith("H_"):
        return True
    if getattr(shape, "is_placeholder", False):
        ph_type = shape.placeholder_format.type
        if ph_type in (1, 3, 13, 15, 16):   # TITLE, CENTER_TITLE, SLIDE_NUMBER, FOOTER, HEADER
            return True
    n = _norm(text)
    return n in boilerplate or n.startswith(_PLACEHOLDER_PREFIXES) or bool(re.fullmatch(r"\d{1,2}", n))


HIDDEN_FONT_PT = 6          # kleiner = praktisch unsichtbar
_LIGHT_RGB_MIN = 0xF0        # alle Kanäle ≥ F0 = (fast) weiss


def _hidden_reason(shape, slide_w: int | None, slide_h: int | None) -> str | None:
    """Warum ein Shape für Lesende unsichtbar ist — oder None."""
    try:
        left, top = shape.left, shape.top
        width, height = shape.width, shape.height
        if slide_w and slide_h and left is not None and top is not None:
            if left + (width or 0) <= 0 or top + (height or 0) <= 0 or left >= slide_w or top >= slide_h:
                return "ausserhalb der Folie"
    except Exception:
        pass
    if not getattr(shape, "has_text_frame", False):
        return None
    try:
        runs = [r for p in shape.text_frame.paragraphs for r in p.runs if r.text.strip()]
    except Exception:
        return None
    if not runs:
        return None
    tiny = white = 0
    for run in runs:
        try:
            if run.font.size is not None and run.font.size.pt < HIDDEN_FONT_PT:
                tiny += 1
        except Exception:
            pass
        try:
            rgb = run.font.color.rgb if run.font.color and run.font.color.type is not None else None
            if rgb is not None and all(int(str(rgb)[i:i + 2], 16) >= _LIGHT_RGB_MIN for i in (0, 2, 4)):
                white += 1
        except Exception:
            pass
    if tiny == len(runs):
        return "winzige Schrift"
    if white == len(runs) and not _has_dark_fill(shape) and not getattr(shape, "is_placeholder", False):
        return "weisse Schrift"
    return None


def _has_dark_fill(shape) -> bool:
    """Weisse Schrift auf dunkler Fläche ist sichtbar (Vorlagen-Kopfzeilen)."""
    try:
        fill = shape.fill
        if fill.type != 1:                     # MSO_FILL.SOLID
            return False
        rgb = str(fill.fore_color.rgb)
        channels = [int(rgb[i:i + 2], 16) for i in (0, 2, 4)]
        return sum(channels) / 3 < 0x90
    except Exception:
        return False


_DGM_NS = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _smartart_text(slide) -> str:
    """Text aus SmartArt-Grafiken der Folie. python-pptx liefert für
    SmartArt nur einen leeren Rahmen; der Text liegt im Diagramm-Datenteil
    (Knoten ``dgm:pt``). Ganze Abgaben kamen so als "kein Text" zurück."""
    from lxml import etree

    lines: list[str] = []
    for rel in slide.part.rels.values():
        if not rel.reltype.endswith("/diagramData"):
            continue
        try:
            root = etree.fromstring(rel.target_part.blob)
        except Exception:
            continue
        for pt in root.iter(f"{{{_DGM_NS}}}pt"):
            paragraphs = [
                "".join(t.text or "" for t in p.iter(f"{{{_A_NS}}}t")).strip()
                for p in pt.iter(f"{{{_A_NS}}}p")
            ]
            lines.extend(p for p in paragraphs if p)
    return "\n".join(lines)


def _is_instruction(text: str) -> bool:
    from backend.briefings.intake import injection_scan  # lazy: intake importiert dieses Modul

    return bool(injection_scan(text))


def _slide_content(slide, boilerplate: set[str], hidden_out: list[dict] | None = None,
                   slide_w: int | None = None, slide_h: int | None = None, own_titles: bool = False) -> str:
    """Text einer Folie ohne Vorlagentexte. ``own_titles``: eigene
    Überschriften im Titelfeld zählen zur Antwort (Baustein-Folien)."""
    parts: list[str] = []
    for shape in slide.shapes:
        reason = _hidden_reason(shape, slide_w, slide_h) if hidden_out is not None else None
        for _, text in _shape_texts(shape):
            if own_titles and _is_title(shape):
                cleaned = _own_title_lines(text, boilerplate)
            elif _is_pptx_boilerplate(shape, text, boilerplate):
                continue
            else:
                cleaned = _strip_boilerplate_lines(text, boilerplate)
            if not cleaned:
                continue
            if reason == "weisse Schrift" and not _is_instruction(cleaned):
                # Weisse Schrift steht meist auf einer dunklen Fläche dahinter
                # (gestaltete Folien) — das ist Antworttext, kein Versteck.
                reason = None
            if reason:
                hidden_out.append({"grund": reason, "text": re.sub(r"\s+", " ", cleaned)[:160]})
                continue
            parts.append(cleaned)
    smartart = _strip_boilerplate_lines(_smartart_text(slide), boilerplate)
    if smartart:
        parts.append(smartart)
    return "\n".join(parts).strip()


def _kenndaten_from_pptx(slide, filename: str) -> tuple[Kenndaten, bool]:
    """Liest die KENN_*-Shapes der Vorlage; Rückgabe (kenndaten, vorlage_erkannt)."""
    fields: dict[str, str] = {}
    for shape in slide.shapes:
        name = (getattr(shape, "name", "") or "").upper()
        if name.startswith("KENN_") and getattr(shape, "has_text_frame", False):
            fields[name] = shape.text_frame.text.strip()
    template = bool(fields)
    kd = Kenndaten()
    # Vom Deckblatt wird AUSSCHLIESSLICH der Code gelesen. Das Namensfeld
    # (KENN_NAMEN) wird nicht angefasst — keine personenbezogenen Daten.
    # Jede Quelle füllt nur, was noch fehlt: Code-Feld → Einzelfelder →
    # übriger Deckblatt-Text → Dateiname.
    _merge_from_text(kd, "kenndaten", fields.get("KENN_CODE", ""))
    sg_match = re.fullmatch(r"\s*(?:SG)?\s*0?([1-8])\s*", fields.get("KENN_SG", "") or "", re.IGNORECASE)
    tp_match = re.fullmatch(r"\s*(?:TP)?\s*([1-5])\s*", fields.get("KENN_TP", "") or "", re.IGNORECASE)
    _merge_kenndaten(
        kd, "kenndaten",
        tp=int(tp_match.group(1)) if tp_match else None,
        ueg=normalize_ueg(fields.get("KENN_UEG", "")),
        sg=int(sg_match.group(1)) if sg_match else None,
    )
    if not (kd.tp and kd.ueg and kd.sg):
        # Nur Nicht-Vorlagen-Shapes: Labels (L_*), Hinweise (H_*) und die
        # Fusszeile (DECK_FUSS) tragen Beispielcodes, keine Kenndaten.
        all_text = "\n".join(
            t for shape in slide.shapes for name, t in _shape_texts(shape)
            if not name.upper().startswith(("L_", "H_", "DECK_", "KOPF_"))
        )
        _merge_from_text(kd, "text", all_text)
    if not (kd.tp and kd.ueg and kd.sg):
        _merge_from_filename(kd, filename)
    if kd.ueg and kd.sg and kd.tp:
        kd.code = build_code(kd.tp, kd.ueg, kd.sg)
    return kd, template


_BAUSTEIN_TITLE_MARK = {
    1: re.compile(r"(?:baustein|building\s+block)\s*1\b", re.IGNORECASE),
    2: re.compile(r"(?:baustein|building\s+block)\s*2\b", re.IGNORECASE),
}


def _baustein_keywords(tp: int | None) -> tuple[set[str], set[str]]:
    """Kennwörter je Baustein aus den Bausteintiteln der Rubric (deutsch und
    englisch), ohne Wörter, die in beiden Titeln vorkommen."""
    words: dict[str, set[str]] = {"baustein1": set(), "baustein2": set()}
    if tp in SUPPORTED_TPS:
        for language in ("de", "en"):
            try:
                rubric = load_rubric(tp, language)
            except ValueError:
                continue
            for b in rubric.bausteine:
                if b.key in words:
                    words[b.key].update(w for w in re.findall(r"[a-zäöüß]{6,}", b.title.lower()))
    common = words["baustein1"] & words["baustein2"]
    return words["baustein1"] - common, words["baustein2"] - common


def _baustein2_start(slides: list, tp: int | None) -> int:
    """Index der ersten Folie von Baustein 2, wenn die Abgabe mehr Folien hat
    als die Vorlage. Massgeblich sind die Bausteintitel der Vorlage und die
    Kennwörter der Rubric je Folie; ohne Anhaltspunkt gilt die Vorlage
    (Folie 2 = Baustein 1, alles danach = Baustein 2)."""
    kw1, kw2 = _baustein_keywords(tp)
    lean: list[int] = []        # > 0: Folie spricht für Baustein 1, < 0: für Baustein 2
    for slide in slides:
        text = "\n".join(t for shape in slide.shapes for _, t in _shape_texts(shape)).lower()
        s1 = sum(1 for k in kw1 if k in text) + 3 * bool(_BAUSTEIN_TITLE_MARK[1].search(text))
        s2 = sum(1 for k in kw2 if k in text) + 3 * bool(_BAUSTEIN_TITLE_MARK[2].search(text))
        lean.append(s1 - s2)
    best, best_score = 2, None
    for start in range(2, len(slides)):
        score = sum(lean[1:start]) - sum(lean[start:])
        if best_score is None or score > best_score:
            best, best_score = start, score
    return best


def extract_pptx(filename: str, data: bytes, expected_tp: int | None = None) -> ExtractedSubmission:
    from pptx import Presentation  # lazy: schwerer Import

    try:
        prs = Presentation(io.BytesIO(data))
        slides = list(prs.slides)
    except Exception as exc:
        raise ValueError("PPTX konnte nicht gelesen werden.") from exc
    if not slides:
        raise ValueError("PPTX enthält keine Folien.")

    boilerplate = _boilerplate_set(expected_tp)
    kd, template = _kenndaten_from_pptx(slides[0], filename)
    sub = ExtractedSubmission(
        filename=filename, format="pptx", kenndaten=kd,
        slide_count=len(slides), template_detected=template,
    )

    if len(slides) >= 3:
        w, h = prs.slide_width, prs.slide_height
        # Mehr Folien als die Vorlage: nichts weglassen, sondern zuordnen
        start2 = _baustein2_start(slides, kd.tp or expected_tp) if len(slides) > 3 else 2

        def _read(part: list) -> str:
            texts = (_slide_content(s, boilerplate, sub.hidden_text, w, h, own_titles=True) for s in part)
            return "\n".join(t for t in texts if t).strip()

        sub.baustein1 = _read(slides[1:start2])
        sub.baustein2 = _read(slides[start2:])
        if sub.hidden_text:
            sub.notes.append(
                f"{len(sub.hidden_text)} Textfeld(er) ausserhalb der Folie oder unlesbar klein — nicht gelesen."
            )
        area = (w or 0) * (h or 0)
        sub.pictures_baustein1 = sum(_picture_count(s.shapes, area) for s in slides[1:start2])
        sub.pictures_baustein2 = sum(_picture_count(s.shapes, area) for s in slides[start2:])
        sub.picture_count = sub.pictures_baustein1 + sub.pictures_baustein2
        if len(slides) > 3:
            def _span(first: int, last: int) -> str:
                return f"Folie {first}" if first == last else f"Folie {first}–{last}"

            sub.notes.append(
                f"Abgabe hat {len(slides)} Folien (Vorlage: 3); {_span(2, start2)} als Baustein 1, "
                f"{_span(start2 + 1, len(slides))} als Baustein 2 gelesen — bitte prüfen."
            )
    else:
        text = "\n".join(_slide_content(s, boilerplate) for s in slides)
        b1, b2, found = split_bausteine(text)
        sub.baustein1, sub.baustein2 = b1, b2
        sub.notes.append(
            f"Abgabe hat nur {len(slides)} Folie(n) (Vorlage: 3); Bausteine "
            + ("über Marker getrennt." if found else "konnten nicht getrennt werden.")
        )
    _finalize(sub)
    return sub


# ---------------------------------------------------------------------------
# DOCX
# ---------------------------------------------------------------------------

def _docx_text(data: bytes) -> str:
    from docx import Document  # lazy
    from docx.oxml.ns import qn

    try:
        doc = Document(io.BytesIO(data))
    except Exception as exc:
        raise ValueError("DOCX konnte nicht gelesen werden.") from exc

    lines: list[str] = []
    body = doc.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            text = "".join(t.text or "" for t in child.iter(qn("w:t")))
            if text.strip():
                lines.append(text)
        elif child.tag == qn("w:tbl"):
            for row in child.iter(qn("w:tr")):
                cells = []
                for cell in row.iter(qn("w:tc")):
                    ctext = " ".join(
                        "".join(t.text or "" for t in p.iter(qn("w:t")))
                        for p in cell.iter(qn("w:p"))
                    ).strip()
                    if ctext:
                        cells.append(ctext)
                if cells:
                    lines.append(" | ".join(cells))
    return "\n".join(lines)


def extract_docx(filename: str, data: bytes, expected_tp: int | None = None) -> ExtractedSubmission:
    text = _docx_text(data)
    if not text.strip():
        raise ValueError("DOCX enthält keinen Text.")
    return _from_flat_text(filename, "docx", text, expected_tp)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def extract_pdf(filename: str, data: bytes, expected_tp: int | None = None) -> ExtractedSubmission:
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as exc:
        raise ValueError("PDF konnte nicht gelesen werden.") from exc
    if not any(pages):
        raise ValueError("PDF enthält keinen extrahierbaren Text (Scan ohne OCR?).")

    boilerplate = _boilerplate_set(expected_tp)
    if len(pages) >= 3:
        # Aus der Vorlage exportiert: Seite 2 = Baustein 1, Seite 3 = Baustein 2.
        kd = _kenndaten_from_text(pages[0], filename)
        sub = ExtractedSubmission(filename=filename, format="pdf", kenndaten=kd, slide_count=len(pages))
        sub.baustein1 = _strip_boilerplate_lines(pages[1], boilerplate)
        sub.baustein2 = _strip_boilerplate_lines(pages[2], boilerplate)
        if len(pages) > 3:
            sub.notes.append(f"PDF hat {len(pages)} Seiten (Vorlage: 3); nur Seite 2 und 3 wurden gelesen.")
        _finalize(sub)
        return sub
    return _from_flat_text(filename, "pdf", "\n".join(pages), expected_tp, page_count=len(pages))


# ---------------------------------------------------------------------------
# Gemeinsam
# ---------------------------------------------------------------------------

def _kenndaten_from_text(text: str, filename: str) -> Kenndaten:
    kd = Kenndaten()
    _merge_from_text(kd, "text", text)
    if not (kd.tp and kd.ueg and kd.sg):
        _merge_from_filename(kd, filename)
    if kd.ueg and kd.sg and kd.tp:
        kd.code = build_code(kd.tp, kd.ueg, kd.sg)
    return kd


def _from_flat_text(
    filename: str, fmt: str, text: str, expected_tp: int | None, page_count: int | None = None
) -> ExtractedSubmission:
    boilerplate = _boilerplate_set(expected_tp)
    kd = _kenndaten_from_text(text[:3000], filename)
    cleaned = _strip_boilerplate_lines(text, boilerplate)
    b1, b2, found = split_bausteine(cleaned)
    sub = ExtractedSubmission(filename=filename, format=fmt, kenndaten=kd, slide_count=page_count)
    sub.baustein1, sub.baustein2 = b1, b2
    if not found:
        sub.notes.append(
            "Keine 'Baustein 1'/'Baustein 2'-Marker gefunden; der gesamte Text wurde Baustein 1 zugeordnet."
        )
    _finalize(sub)
    return sub


# ---------------------------------------------------------------------------
# Personenbezogene Daten (Owner-Entscheidung 2026-09-14): E-Mail-Adressen,
# Matrikelnummern, Telefonnummern und Zeilen wie "Name: …" verschwinden aus
# dem Baustein-Text, BEVOR er gespeichert oder an ein Modell geschickt wird.
# ---------------------------------------------------------------------------

_PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("email", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.IGNORECASE)),
    ("matrikel", re.compile(r"\b\d{2}[-. ]\d{3}[-. ]\d{3}\b")),            # HSG-Format 12-345-678
    ("matrikel", re.compile(r"\bmatrikel(?:nummer|nr\.?)?\s*[:#]?\s*\d{6,9}\b", re.IGNORECASE)),
    ("telefon", re.compile(r"(?<!\d)(?:\+\d{2}|0)\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}(?!\d)")),
]
_PII_LINE = re.compile(
    r"^\s*(?:name[n]?|vorname|nachname|mitglied(?:er)?|teilnehmer(?:in|innen)?|student(?:in|innen)?|"
    r"matrikel(?:nummer|nr\.?)?|e-?mail|telefon|tel\.?)\s*[:：]",
    re.IGNORECASE,
)


def scrub_personal_data(text: str) -> tuple[str, list[str]]:
    """Entfernt personenbezogene Angaben; Rückgabe (Text, Labels der Funde)."""
    hits: set[str] = set()
    kept: list[str] = []
    for line in (text or "").splitlines():
        if _PII_LINE.match(line):
            hits.add("namenszeile")
            continue
        cleaned = line
        for label, pattern in _PII_PATTERNS:
            if pattern.search(cleaned):
                hits.add(label)
                cleaned = pattern.sub("[entfernt]", cleaned)
        kept.append(cleaned)
    return "\n".join(kept).strip(), sorted(hits)


def _finalize(sub: ExtractedSubmission) -> None:
    for key in ("baustein1", "baustein2"):
        text, hits = scrub_personal_data(getattr(sub, key))
        sub.pii_hits = sorted(set(sub.pii_hits) | set(hits))
        if len(text) > MAX_BAUSTEIN_CHARS:
            sub.notes.append(f"{key}: Text auf {MAX_BAUSTEIN_CHARS} Zeichen gekürzt.")
            text = text[:MAX_BAUSTEIN_CHARS]
        setattr(sub, key, text)                      # bereinigt UND ggf. gekürzt — immer zurückschreiben
        setattr(sub, f"{key}_chars", count_chars(text))


def extract_submission(filename: str, data: bytes, expected_tp: int | None = None) -> ExtractedSubmission:
    """Dispatch nach Dateiendung; ValueError bei unlesbarer Datei."""
    lower = filename.lower()
    if lower.endswith(".pptx"):
        return extract_pptx(filename, data, expected_tp)
    if lower.endswith(".docx"):
        return extract_docx(filename, data, expected_tp)
    if lower.endswith(".pdf"):
        return extract_pdf(filename, data, expected_tp)
    raise ValueError("Nicht unterstütztes Format (erlaubt: pptx, docx, pdf).")
