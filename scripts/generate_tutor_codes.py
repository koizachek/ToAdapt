"""Erzeugt Einzelzugangscodes für Tutor:innen (Teacher-Login).

Ausgabe: (1) CSV mit kennung;code zur Verteilung, (2) der Wert für die
Env-Variable TEACHER_ACCESS_CODES (JSON) — in Vercel setzen (server-only,
niemals NEXT_PUBLIC_*). Codes sind tippfreundlich (kein 0/O/1/l).

Aufrufe:
    python scripts/generate_tutor_codes.py --count 40
    python scripts/generate_tutor_codes.py --names tutoren.txt   # eine Kennung pro Zeile
    python scripts/generate_tutor_codes.py --count 40 --csv tutor_codes.csv

Rotation einzelner Codes: Skript mit --names <nur diese Kennung> erneut
laufen lassen und den Eintrag im JSON ersetzen.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path

# Ohne verwechselbare Zeichen (0/O, 1/l/I).
ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def make_code() -> str:
    chunk = lambda: "".join(secrets.choice(ALPHABET) for _ in range(4))  # noqa: E731
    return f"{chunk()}-{chunk()}-{chunk()}"


def generate(names: list[str]) -> dict[str, str]:
    codes: dict[str, str] = {}
    used: set[str] = set()
    for name in names:
        key = name.strip()
        if not key or key in codes:
            continue
        code = make_code()
        while code in used:
            code = make_code()
        used.add(code)
        codes[key] = code
    return codes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--count", type=int, help="Anzahl Codes (Kennungen tutor01…tutorNN)")
    group.add_argument("--names", type=Path, help="Datei mit einer Tutor-Kennung pro Zeile")
    parser.add_argument("--csv", type=Path, default=None, help="CSV-Ausgabedatei (kennung;code)")
    args = parser.parse_args()

    if args.names:
        names = args.names.read_text(encoding="utf-8").splitlines()
    else:
        width = max(2, len(str(args.count)))
        names = [f"tutor{i:0{width}d}" for i in range(1, args.count + 1)]

    codes = generate(names)
    if not codes:
        print("Keine Kennungen gefunden.", file=sys.stderr)
        return 1

    if args.csv:
        lines = ["kennung;code"] + [f"{name};{code}" for name, code in codes.items()]
        args.csv.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"CSV -> {args.csv}  ({len(codes)} Codes)")
    else:
        for name, code in codes.items():
            print(f"{name};{code}")

    print("\nTEACHER_ACCESS_CODES (in Vercel als Env-Variable setzen):")
    print(json.dumps(codes, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
