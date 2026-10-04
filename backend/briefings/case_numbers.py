"""Zahlenabgleich der Abgabe mit dem Fallmaterial — im Code, nicht im Modell.

Owner-Entscheidung 2026-10-02: Die Faktenprüfung fragt nicht «stimmt die
Zahl der Gruppe?», sondern «kommt diese Zahl irgendwo im Fall vor?» (alle
Kapitel, beide Sprachen, inklusive Exhibits). Kommt sie vor, gibt es keine
Meldung. Kommt sie nicht vor, meldet das Briefing neutral «Im Fall nicht
gefunden: …» — ohne Gegenzahl. Hintergrund: Das Modell stellte Zahlen der
Gruppen falsche oder erfundene Gegenzahlen gegenüber und behandelte Zahlen,
die im Fall fehlen, als Fehler (Lauf vom 2026-10-02: 5 von 7 Beanstandungen).

Geprüft werden nur Zahlen, bei denen ein Fallbezug plausibel ist: Prozent-
werte, Dezimalzahlen und Werte ab 1000 (Beträge, Jahre, Belegschaft). Kleine
Ganzzahlen («zwei Herausforderungen», «15 Jahre», «Folie 2») bleiben aussen vor.
"""

from __future__ import annotations

import re
from functools import lru_cache

from backend.briefings.rubrics import TP_CHAPTER, load_case_chapter

# Zahl mit optionalen Tausendertrennern (. , ' ’ geschütztes/schmales Leerzeichen)
# und optionalem Dezimalteil, optional gefolgt von einem Prozentzeichen.
_NUMBER_RE = re.compile(
    r"(?<![\w.,])"
    r"(\d{1,3}(?:[.,'’’  ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
    r"(\s?%)?"
    r"(?![\w])"
)
_SEPARATOR_RE = re.compile(r"[.,'’’  ]")


def normalize_number(token: str) -> str:
    """Kanonische Form einer Zahl: ohne Tausendertrenner, Dezimalpunkt.

    Ein Trenner, dem genau drei Ziffern folgen und keine weitere Ziffer, ist
    ein Tausendertrenner («3.000», «3'250», «1,222»); jeder andere Trenner
    ist ein Dezimaltrenner («18,8», «16.7»). «12.000» → «12000», «0.5» → «0.5»."""
    parts = _SEPARATOR_RE.split(token.strip())
    if len(parts) == 1:
        return parts[0].lstrip("0") or "0"
    integer = parts[0]
    decimal = ""
    for part in parts[1:]:
        if len(part) == 3 and not decimal:
            integer += part
        else:
            decimal += part
    integer = integer.lstrip("0") or "0"
    decimal = decimal.rstrip("0")
    return f"{integer}.{decimal}" if decimal else integer


def extract_numbers(text: str) -> list[tuple[str, str]]:
    """Prüfwürdige Zahlen eines Textes in Reihenfolge ihres Auftretens:
    (Schreibweise der Gruppe, kanonische Form), ohne Dubletten."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for match in _NUMBER_RE.finditer(text or ""):
        raw, percent = match.group(1), match.group(2)
        key = normalize_number(raw)
        try:
            value = float(key)
        except ValueError:
            continue
        if not (percent or "." in key or value >= 1000):
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append((raw + ("%" if percent else ""), key))
    return out


@lru_cache(maxsize=1)
def case_number_index() -> frozenset[str]:
    """Alle Zahlen des gesamten Fallmaterials (alle Kapitel, deutsch und
    englisch) in kanonischer Form."""
    keys: set[str] = set()
    for language in ("de", "en"):
        for letter in ("0_einfuehrung", *TP_CHAPTER.values()):
            for match in _NUMBER_RE.finditer(load_case_chapter(letter, language)):
                keys.add(normalize_number(match.group(1)))
    return frozenset(keys)


def numbers_not_in_case(text: str) -> list[str]:
    """Zahlen der Abgabe, die nirgends im Fallmaterial vorkommen — in der
    Schreibweise der Gruppe, als Material für die neutrale Meldung."""
    index = case_number_index()
    return [raw for raw, key in extract_numbers(text) if key not in index]


__all__ = ["case_number_index", "extract_numbers", "normalize_number", "numbers_not_in_case"]
