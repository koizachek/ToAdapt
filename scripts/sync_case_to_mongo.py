"""Upsertet kuratierte Pool-Case(s) aus der Datei nach MongoDB.

Hintergrund: Bei konfiguriertem MongoDB ist Mongo die PRIMÄRE Quelle
(backend/cases/manager.py::get liest Mongo zuerst, Datei nur als Fallback).
Eine reine Datei-Änderung in backend/cases/pool/*.json wirkt daher NICHT live,
solange derselbe Case in Mongo liegt. Dieses Skript liest den Case aus der
Datei (= neuer Stand) und schreibt ihn per Upsert nach Mongo.

ACHTUNG: läuft gegen die MongoDB, die in der geladenen .env (MONGODB_*)
konfiguriert ist — also ggf. die Produktions-DB. Bewusst ausführen.

Nutzung:
    python scripts/sync_case_to_mongo.py alpes-bank-genai-001
    python scripts/sync_case_to_mongo.py --all
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")
sys.path.insert(0, str(REPO_ROOT))

from backend.cases.manager import POOL_DIR, case_manager  # noqa: E402
from backend.models.case import Case  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pool-Case(s) aus der Datei nach MongoDB upserten."
    )
    parser.add_argument("case_id", nargs="?", help="case_id (Dateiname ohne .json)")
    parser.add_argument("--all", action="store_true", help="alle Pool-Cases synchronisieren")
    args = parser.parse_args()

    if not args.all and not args.case_id:
        parser.error("case_id angeben oder --all verwenden")

    mongo_on = case_manager._collection() is not None
    if not mongo_on:
        print("⚠️  Kein MongoDB konfiguriert (MONGODB_* fehlt) — es wird nur die "
              "Datei neu geschrieben, KEIN Mongo-Upsert.")

    if args.all:
        files = [f for f in sorted(POOL_DIR.glob("*.json")) if not f.name.endswith("-agent.json")]
    else:
        f = POOL_DIR / f"{args.case_id}.json"
        if not f.exists():
            parser.error(f"Datei nicht gefunden: {f}")
        files = [f]

    for f in files:
        case = Case.model_validate_json(f.read_text(encoding="utf-8"))
        case_manager.save(case)  # replace_one(upsert) nach Mongo + Datei-write-through
        print(f"✔ {f.stem} → {'Mongo + Datei' if mongo_on else 'nur Datei'}")

    print(f"Fertig: {len(files)} Case(s).")


if __name__ == "__main__":
    main()
