#!/usr/bin/env python3
"""Analysiert einen JSON-Export der Mongo-Collection `experiment_events`.

Input: eine Datei, entweder
  - JSON-Array von Event-Dokumenten (z.B. `mongoexport --jsonArray` oder
    ein pymongo-Dump), oder
  - JSON-Lines (ein Dokument pro Zeile, Standard-`mongoexport`).

Dokument-Schema (geschrieben von MongoExperimentLogger.log_event in
backend/db/experiment_logger.py):
  { "event_type": str, "created_at": datetime, "payload": {...} }
created_at wird als ISO-String oder Mongo-Extended-JSON ({"$date": ...})
akzeptiert.

Ausgabe:
  - Event-Typ-Verteilung (gesamt und pro Tag)
  - Agent-Verteilung über chat_turn_completed (payload.agent_type)
  - Turns pro Session (Ø / Median / Max über payload.session_id)
  - Guardrail-Trigger: INFERIERT über exakten Textvergleich der
    assistant_message mit den festen Fallback-Texten aus
    backend/agents/orchestrator.py (_guardrail_fallback). Die Mongo-Events
    enthalten den Guardrail-Grund NICHT — der reason-Code steht nur im
    strukturierten Log-Event `guardrail_triggered` (Railway-Logs).
    ACHTUNG: Die Fallback-Texte sind hier eingebettet und müssen bei
    Änderungen an orchestrator.py nachgezogen werden.

Nur Standardbibliothek, keine Schreibzugriffe, keine Netzwerkzugriffe.

Usage:
  python3 analyze_experiment_events.py events_export.json
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Feste Guardrail-Fallback-Texte (Stand 2026-07-08) — exakte Kopien aus
# backend/agents/orchestrator.py, _guardrail_fallback(). Bei Treffer wurde die
# Original-Agent-Antwort durch den Guardrail-Layer ersetzt.
GUARDRAIL_FALLBACK_TEXTS = {
    # DE
    "Kurz erklärt: Konzentriere dich auf die Grundlogik des Begriffs und frage dich dann, "
    "welche sichtbare Spannung im Case damit beschrieben wird. Welche Rolle spielt der Begriff "
    "hier für die Entscheidung oder das Geschäftsmodell?",
    "Halte deine Antwort knapp: erst die Kernbehauptung, dann die Begründung, dann die Konsequenz. "
    "Welche eine Aussage ist bei dir gerade wirklich zentral?",
    "Ich bleibe hier lieber bei der Denkstruktur statt dir eine fertige Richtung vorzugeben: "
    "Welche zwei Kriterien oder Spannungen sind aus dem Case sicher belegt, und wie würden sie "
    "deine Entscheidung verändern?",
    # EN
    "Briefly: focus on the basic logic of the term and then ask which visible tension "
    "in the case it describes. What role does the term play here for the decision or "
    "the business model?",
    "Keep your answer concise: first the core claim, then the reasoning, then the consequence. "
    "Which one statement is truly central right now?",
    "I will stay with the thinking structure rather than giving you a finished direction: "
    "which two criteria or tensions are clearly supported by the case, and how would they "
    "change your decision?",
}


def _load_events(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        data = json.loads(text)
        return [d for d in data if isinstance(d, dict)]
    # JSON-Lines
    events = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            doc = json.loads(line)
        except Exception:
            continue
        if isinstance(doc, dict):
            events.append(doc)
    return events


def _event_day(doc: dict) -> str:
    raw = doc.get("created_at")
    if isinstance(raw, dict):  # Mongo Extended JSON: {"$date": "..."} oder {"$date": {"$numberLong": ...}}
        raw = raw.get("$date")
        if isinstance(raw, dict):
            raw = raw.get("$numberLong")
            if raw is not None:
                from datetime import datetime, timezone
                return datetime.fromtimestamp(int(raw) / 1000, tz=timezone.utc).date().isoformat()
    if isinstance(raw, str) and len(raw) >= 10:
        return raw[:10]
    return "unbekannt"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2

    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"Datei nicht gefunden: {path}", file=sys.stderr)
        return 1

    events = _load_events(path)
    if not events:
        print("Keine Events im Export gefunden.")
        return 1

    type_counts = Counter(str(e.get("event_type", "?")) for e in events)
    day_counts: dict[str, Counter] = defaultdict(Counter)
    for e in events:
        day_counts[_event_day(e)][str(e.get("event_type", "?"))] += 1

    chat_events = [e for e in events if e.get("event_type") == "chat_turn_completed"]
    agent_counts = Counter(
        str((e.get("payload") or {}).get("agent_type", "?")) for e in chat_events
    )
    turns_per_session = Counter(
        str((e.get("payload") or {}).get("session_id", "?")) for e in chat_events
    )
    guardrail_hits = [
        e for e in chat_events
        if str((e.get("payload") or {}).get("assistant_message", "")).strip()
        in GUARDRAIL_FALLBACK_TEXTS
    ]
    guardrail_by_day = Counter(_event_day(e) for e in guardrail_hits)

    print("== experiment_events — Analyse ==")
    print(f"Events gesamt: {len(events)}")
    print("\n-- Event-Typ-Verteilung --")
    for etype, n in type_counts.most_common():
        print(f"  {etype:<28}{n:>6}")

    print("\n-- Events pro Tag --")
    for day in sorted(day_counts):
        total = sum(day_counts[day].values())
        print(f"  {day}: {total}")

    if chat_events:
        print("\n-- Agent-Verteilung (chat_turn_completed) --")
        for agent, n in agent_counts.most_common():
            print(f"  {agent:<16}{n:>6}  ({n / len(chat_events) * 100:.1f} %)")

        turns = sorted(turns_per_session.values())
        print("\n-- Turns pro Session --")
        print(f"  Sessions: {len(turns)}")
        print(f"  Ø:        {sum(turns) / len(turns):.2f}")
        print(f"  Median:   {statistics.median(turns):.1f}")
        print(f"  Max:      {max(turns)}")

        print("\n-- Guardrail-Trigger (inferiert über Fallback-Text-Match) --")
        print(f"  Gesamt: {len(guardrail_hits)}/{len(chat_events)} Chat-Turns"
              f" ({len(guardrail_hits) / len(chat_events) * 100:.1f} %)")
        for day in sorted(guardrail_by_day):
            print(f"  {day}: {guardrail_by_day[day]}")
        if not guardrail_hits:
            print("  (keine — oder Fallback-Texte im Skript sind nicht mehr aktuell)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
