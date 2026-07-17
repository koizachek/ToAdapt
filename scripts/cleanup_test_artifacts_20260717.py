"""Einmaliges Cleanup: Test-Artefakte des 2026-07-17 aus der Produktions-DB entfernen.

Zwei lokale pytest-Läufe (vor Einführung von tests/conftest.py) haben über die
Root-.env in die Produktions-Collections geschrieben: 14 submission_states
(user_id u-test / matrikelnummer test-9999 bzw. zwei anon-Hashes aus dem
Pseudonymisierungs-Test), 2 sessions (user-42) und 32 experiment_events —
alle in den Fenstern 09:02Z und 09:08Z. Dieses Skript löscht exakt das
Zeitfenster [08:30Z, 09:15Z) des 2026-07-17.

Erst prüfen, dann löschen:

    python scripts/cleanup_test_artifacts_20260717.py            # nur anzeigen
    python scripts/cleanup_test_artifacts_20260717.py --delete   # löschen
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.db import mongo  # noqa: E402

WINDOW_START = "2026-07-17T08:30:00"
WINDOW_END = "2026-07-17T09:15:00"
DT_START = datetime(2026, 7, 17, 8, 30)
DT_END = datetime(2026, 7, 17, 9, 15)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delete", action="store_true", help="Wirklich löschen (Default: nur anzeigen).")
    args = parser.parse_args()

    if not mongo.mongo_enabled():
        print("FEHLER: MongoDB ist nicht konfiguriert.")
        return 1

    # started_at ist als ISO-String gespeichert, created_at als BSON-Datum.
    targets = [
        ("submission_states", {"started_at": {"$gte": WINDOW_START, "$lt": WINDOW_END}}),
        ("sessions", {"started_at": {"$gte": WINDOW_START, "$lt": WINDOW_END}}),
        ("experiment_events", {"created_at": {"$gte": DT_START, "$lt": DT_END}}),
    ]
    for name, flt in targets:
        collection = mongo.get_collection(name)
        if collection is None:
            print(f"FEHLER: Collection {name} nicht erreichbar.")
            return 1
        count = collection.count_documents(flt)
        if args.delete:
            deleted = collection.delete_many(flt).deleted_count
            print(f"{name}: {deleted} gelöscht (Rest: {collection.count_documents({})})")
        else:
            print(f"{name}: {count} Treffer im Fenster (nichts gelöscht — --delete zum Ausführen)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
