"""MongoDB-TTL-Indizes und Backfill für das Löschkonzept anlegen.

Setzt das Lösch- und Aufbewahrungskonzept des Datenschutzantrags um
(Teil 1 Lehrbetrieb, Abschnitt 7; Teil 2 Forschung, Abschnitt 5):

- Formative Lehrbetriebs-Daten (sessions, submission_states,
  dashboard_results, group_uploads): Löschung Semesterende + 4 Wochen.
- Forschungslog (experiment_events): Löschung längstens 24 Monate nach
  Semesterende.

Pro Collection wird ein TTL-Index (expireAfterSeconds=0) auf dem Feld
`expire_at` angelegt und Bestandsdokumente ohne dieses Feld werden auf den
jeweiligen Termin gesetzt (Backfill). Neue Dokumente erhalten `expire_at`
direkt von den Stores (backend/db/*). Die Termine kommen aus
backend/config/retention.py und sind per RETENTION_FORMATIVE_EXPIRE_AT /
RETENTION_RESEARCH_EXPIRE_AT überschreibbar.

Zusätzlich legt das Skript die Lookup-Indizes aus ROLLOUT_CHECKLIST W1 an
(sessions.session_id, submission_states.submission_id,
dashboard_results.{submission_id, matrikelnummer, group_code},
cases.case_id, experiment_events.{event_type, created_at}).

ACHTUNG: Das Skript wirkt auf die per Env (.env / MONGODB_*) konfigurierte
Datenbank — der MongoDB-TTL-Monitor beginnt nach dem Lauf, abgelaufene
Dokumente unwiderruflich zu löschen. Erst mit --dry-run prüfen:

    python scripts/ensure_mongo_indexes.py --dry-run
    python scripts/ensure_mongo_indexes.py
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.config import retention  # noqa: E402
from backend.db import mongo  # noqa: E402

TTL_INDEX_NAME = "ttl_expire_at"


def collection_plan() -> list[tuple[str, datetime]]:
    """(Collection-Name, Löschtermin) pro Collection — Env-Namen wie in den Stores."""
    formative = retention.formative_expire_at()
    research = retention.research_expire_at()
    return [
        (os.environ.get("MONGODB_SESSIONS_COLLECTION", "sessions"), formative),
        (os.environ.get("MONGODB_SUBMISSIONS_COLLECTION", "submission_states"), formative),
        (os.environ.get("MONGODB_DASHBOARD_COLLECTION", "dashboard_results"), formative),
        (os.environ.get("MONGODB_GROUP_UPLOADS_COLLECTION", "group_uploads"), formative),
        (os.environ.get("MONGODB_COLLECTION", "experiment_events"), research),
    ]


def lookup_index_plan() -> list[tuple[str, list[str]]]:
    """(Collection-Name, Indexfelder) der Abfrage-Indizes aus ROLLOUT_CHECKLIST W1."""
    return [
        (os.environ.get("MONGODB_SESSIONS_COLLECTION", "sessions"), ["session_id"]),
        (os.environ.get("MONGODB_SUBMISSIONS_COLLECTION", "submission_states"), ["submission_id"]),
        (
            os.environ.get("MONGODB_DASHBOARD_COLLECTION", "dashboard_results"),
            ["submission_id", "matrikelnummer", "group_code"],
        ),
        ("cases", ["case_id"]),
        (os.environ.get("MONGODB_COLLECTION", "experiment_events"), ["event_type", "created_at"]),
    ]


def ensure_lookup_indexes(collection, fields: list[str], dry_run: bool) -> list[str]:
    """Legt fehlende Einzelfeld-Indizes an; gibt die neu angelegten Namen zurück."""
    existing = {
        key[0][0]
        for key in (idx["key"] for idx in collection.index_information().values())
        if len(key) == 1
    }
    created: list[str] = []
    for field in fields:
        if field in existing:
            continue
        if not dry_run:
            collection.create_index(field, name=f"idx_{field}")
        created.append(field)
    return created


def ensure_ttl(collection, expire_at: datetime, dry_run: bool) -> dict:
    """Legt den TTL-Index an und setzt fehlende expire_at-Felder (Backfill)."""
    missing = collection.count_documents({retention.TTL_FIELD: {"$exists": False}})
    has_index = TTL_INDEX_NAME in collection.index_information()

    if dry_run:
        return {"missing_expire_at": missing, "index_exists": has_index, "changed": False}

    if not has_index:
        collection.create_index(
            retention.TTL_FIELD, expireAfterSeconds=0, name=TTL_INDEX_NAME
        )
    backfilled = 0
    if missing:
        result = collection.update_many(
            {retention.TTL_FIELD: {"$exists": False}},
            {"$set": {retention.TTL_FIELD: expire_at}},
        )
        backfilled = result.modified_count
    return {"missing_expire_at": missing, "index_exists": has_index, "backfilled": backfilled, "changed": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur berichten (fehlende expire_at-Felder, Index-Status), nichts schreiben.",
    )
    args = parser.parse_args()

    if not mongo.mongo_enabled():
        print("FEHLER: MongoDB ist nicht konfiguriert (MONGODB_URI bzw. MAS_*/HOST setzen).")
        return 1

    print(f"Datenbank: {mongo.database_name()}  (dry_run={args.dry_run})")
    for name, expire_at in collection_plan():
        collection = mongo.get_collection(name)
        if collection is None:
            print(f"FEHLER: Collection {name} nicht erreichbar.")
            return 1
        info = ensure_ttl(collection, expire_at, args.dry_run)
        print(
            f"  {name}: Löschtermin {expire_at.date().isoformat()}, "
            f"Index vorhanden: {info['index_exists']}, "
            f"Dokumente ohne expire_at: {info['missing_expire_at']}"
            + (f", nachgetragen: {info['backfilled']}" if info["changed"] else "")
        )
    for name, fields in lookup_index_plan():
        collection = mongo.get_collection(name)
        if collection is None:
            print(f"FEHLER: Collection {name} nicht erreichbar.")
            return 1
        created = ensure_lookup_indexes(collection, fields, args.dry_run)
        if created:
            verb = "fehlend" if args.dry_run else "angelegt"
            print(f"  {name}: Lookup-Indizes {verb}: {', '.join(created)}")

    if args.dry_run:
        print("Dry-Run: nichts geschrieben. Ohne --dry-run erneut ausführen zum Anlegen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
