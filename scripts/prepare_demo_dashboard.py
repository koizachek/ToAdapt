"""Demo-Daten fürs Tutor-Dashboard aus den Original-Erhebungsdaten.

Nimmt Dashboard-Ergebnis-JSONs der Erhebung (liegen NUR im sicheren
lokalen Speicher, z.B. ~/ToAdapt_sensitive_data/backend/db/submissions/),
entfernt ALLE personenbezogenen Spuren und verteilt die Personen auf
Demo-Gruppen — die echten Score-Verteilungen, Schwächen und Feedbacks
bleiben erhalten, damit das Dashboard realistisch wirkt.

Sanitisierung:
- matrikelnummer → deterministisches Demo-Pseudonym (demo-001, demo-002 …)
- experiment-Feld (Prolific-IDs) wird KOMPLETT entfernt
- group_code → Round-Robin über --groups (Default DEMO-G1…DEMO-G4)
- Marker "demo": true an jedem Dokument (für rückstandsfreies Entfernen)
- PII-Wächter: bricht ab, falls im Output noch eine Original-Kennung oder
  ein 24-Hex-Muster (Prolific-PID-Form) auftaucht.

Aufrufe:
    # 1) Sanitisieren (schreibt Demo-JSONs, fasst Originale nie an)
    python scripts/prepare_demo_dashboard.py ~/ToAdapt_sensitive_data/backend/db/submissions \\
        --output-dir /tmp/toadapt_demo

    # 2) Lokal anzeigen: Output in den Datei-Store legen
    python scripts/prepare_demo_dashboard.py <input> --publish-files

    # 3) In die DEPLOYTE Umgebung laden (MONGODB_URI der Prod-DB setzen!)
    MONGODB_URI='mongodb+srv://…' python scripts/prepare_demo_dashboard.py <input> --publish-mongo

    # 4) Vor dem echten Semesterstart: alle Demo-Daten entfernen
    MONGODB_URI='…' python scripts/prepare_demo_dashboard.py --remove
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.db import mongo  # noqa: E402

FILE_STORE = REPO_ROOT / "backend" / "db" / "submissions"
DEFAULT_GROUPS = ["DEMO-G1", "DEMO-G2", "DEMO-G3", "DEMO-G4"]
HEX24 = re.compile(r"\b[0-9a-f]{24}\b")


def sanitize_results(results: list[dict], groups: list[str]) -> list[dict]:
    """Pseudonymisiert, gruppiert und markiert die Ergebnisse als Demo."""
    pseudonyms: dict[str, str] = {}
    sanitized: list[dict] = []

    for result in sorted(results, key=lambda r: str(r.get("matrikelnummer", ""))):
        original_id = str(result.get("matrikelnummer", ""))
        if original_id not in pseudonyms:
            pseudonyms[original_id] = f"demo-{len(pseudonyms) + 1:03d}"
        demo_id = pseudonyms[original_id]
        member_index = int(demo_id.split("-")[1]) - 1

        out = {key: value for key, value in result.items() if key != "experiment"}
        out["matrikelnummer"] = demo_id
        out["submission_id"] = f"demo-{out.get('submission_id', '')}"
        out["group_code"] = groups[member_index % len(groups)]
        out["demo"] = True
        sanitized.append(out)

    _guard_no_pii(sanitized, set(pseudonyms.keys()))
    return sanitized


def _guard_no_pii(sanitized: list[dict], original_ids: set[str]) -> None:
    """Wächter: keine Original-Kennungen/PID-Muster/Prolific-Felder im Output."""
    blob = json.dumps(sanitized, ensure_ascii=False)
    for original in original_ids:
        if original and original in blob:
            raise SystemExit(f"ABBRUCH: Original-Kennung noch im Output ({original[:6]}…)")
    if HEX24.search(blob):
        raise SystemExit("ABBRUCH: 24-Hex-Muster (PID-Form) im Output gefunden.")
    if "prolific" in blob.lower():
        raise SystemExit("ABBRUCH: 'prolific' im Output gefunden.")


def load_inputs(input_dir: Path) -> list[dict]:
    results = []
    for path in sorted(input_dir.glob("*.json")):
        try:
            results.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            print(f"WARN: {path.name} unlesbar ({exc})", file=sys.stderr)
    return results


def remove_demo_data() -> None:
    removed_files = 0
    for path in FILE_STORE.glob("demo-*.json"):
        path.unlink()
        removed_files += 1
    print(f"Datei-Store: {removed_files} Demo-Dateien entfernt.")

    collection = mongo.get_collection("dashboard_results")
    if collection is None:
        print("Mongo nicht konfiguriert/erreichbar — nur Datei-Store bereinigt.")
        return
    outcome = collection.delete_many({"demo": True})
    print(f"Mongo dashboard_results: {outcome.deleted_count} Demo-Dokumente entfernt.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path, nargs="?",
                        help="Verzeichnis mit Original-Ergebnis-JSONs (sicherer Speicher)")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Sanitisierte JSONs hier ablegen (Default: nur publish)")
    parser.add_argument("--groups", default=",".join(DEFAULT_GROUPS),
                        help="Kommagetrennte Demo-Gruppencodes")
    parser.add_argument("--publish-files", action="store_true",
                        help="in den lokalen Datei-Store (backend/db/submissions) legen")
    parser.add_argument("--publish-mongo", action="store_true",
                        help="in die Mongo-Collection dashboard_results schreiben (MONGODB_URI!)")
    parser.add_argument("--remove", action="store_true",
                        help="alle Demo-Daten entfernen (Dateien + Mongo, demo=true)")
    args = parser.parse_args()

    if args.remove:
        remove_demo_data()
        return 0

    if not args.input_dir:
        parser.error("input_dir fehlt (oder --remove verwenden)")

    results = load_inputs(args.input_dir)
    if not results:
        print("Keine Eingabedaten gefunden.", file=sys.stderr)
        return 1

    groups = [g.strip() for g in args.groups.split(",") if g.strip()]
    sanitized = sanitize_results(results, groups)
    members = {r["matrikelnummer"] for r in sanitized}
    print(f"{len(sanitized)} Submissions von {len(members)} Personen → "
          f"{len(groups)} Demo-Gruppen. PII-Wächter: bestanden.")

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for result in sanitized:
            (args.output_dir / f"{result['submission_id']}.json").write_text(
                json.dumps(result, ensure_ascii=False), encoding="utf-8"
            )
        print(f"Output → {args.output_dir}")

    if args.publish_files:
        FILE_STORE.mkdir(parents=True, exist_ok=True)
        for result in sanitized:
            (FILE_STORE / f"{result['submission_id']}.json").write_text(
                json.dumps(result, ensure_ascii=False), encoding="utf-8"
            )
        print(f"Datei-Store → {FILE_STORE} ({len(sanitized)} Dateien)")

    if args.publish_mongo:
        collection = mongo.get_collection("dashboard_results")
        if collection is None:
            print("FEHLER: Mongo nicht konfiguriert/erreichbar (MONGODB_URI setzen).",
                  file=sys.stderr)
            return 1
        for result in sanitized:
            collection.replace_one(
                {"submission_id": result["submission_id"]}, result, upsert=True
            )
        print(f"Mongo dashboard_results: {len(sanitized)} Demo-Dokumente publiziert.")

    if not (args.output_dir or args.publish_files or args.publish_mongo):
        print("Hinweis: kein Ziel gewählt (--output-dir / --publish-files / --publish-mongo).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
