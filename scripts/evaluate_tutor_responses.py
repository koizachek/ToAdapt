"""Bewertet Tutor-Antworten pädagogisch nach der NAACL-2025-Taxonomie.

Framework: Maurya et al. (NAACL 2025), "Unifying AI Tutor Evaluation" —
acht Dimensionen, LLM-as-Judge (Details: backend/evaluator/tutor_eval.py).

Quelle sind die geloggten Experiment-Events (chat_turn_completed, optional
formative_feedback_requested) — der Live-Betrieb bleibt unberührt.

Aufrufe:
    # LLM-Judge über alle Chat-Turns eines Event-Exports (kostet LLM-Calls!)
    python scripts/evaluate_tutor_responses.py --events data/experiment_events.json

    # Nur zeigen, was bewertet würde (keine LLM-Calls)
    python scripts/evaluate_tutor_responses.py --events ... --dry-run

    # Blindes Annotations-Workbook für menschliche Validierung erzeugen
    python scripts/evaluate_tutor_responses.py --events ... --annotation-workbook

    # Vorhandene Judge-Ergebnisse (JSONL) nur neu aggregieren
    python scripts/evaluate_tutor_responses.py --aggregate-only <results.jsonl>

Outputs (--output-dir, Default data/prolific_runs/derived/tutor_eval):
    tutor_eval_<ts>.jsonl           eine Zeile pro Turn (Labels + Begründungen)
    tutor_eval_<ts>_summary.json    Aggregation (Desirability je Dimension/Agent)
    tutor_eval_<ts>_summary.csv     dieselbe Aggregation, semikolon-separiert
    tutor_annotation_<ts>_blind.xlsx  Human-Annotation (bei --annotation-workbook)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.evaluator.tutor_eval import (  # noqa: E402
    TUTOR_EVAL_DIMENSIONS,
    TutorResponseEvaluator,
    aggregate_annotations,
)
from backend.llm import get_openrouter_key  # noqa: E402

DEFAULT_EVENTS = REPO_ROOT / "data" / "experiment_events.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "prolific_runs" / "derived" / "tutor_eval"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _payload(event: dict) -> dict:
    """Events kommen als {event_type, payload:{...}} (Mongo-Export) oder flach."""
    payload = event.get("payload")
    return payload if isinstance(payload, dict) else event


def extract_tutor_items(events: list[dict], *, include_feedback: bool = False) -> list[dict]:
    """Baut Bewertungs-Items aus den Events.

    tutor_item_id ist stabil: "{session_id}:{laufende_nr:03d}" für Chat-Turns
    bzw. "{submission_id}:{question_id}:{request_number}" für Denkanstöße —
    damit sind LLM-Judge-Ergebnisse und Human-Annotation joinbar.
    """
    items: list[dict] = []
    per_session: dict[str, int] = {}

    for event in events:
        event_type = event.get("event_type") or _payload(event).get("event_type")
        payload = _payload(event)

        if event_type == "chat_turn_completed":
            session_id = str(payload.get("session_id", "unknown"))
            per_session[session_id] = per_session.get(session_id, 0) + 1
            items.append({
                "tutor_item_id": f"{session_id}:{per_session[session_id]:03d}",
                "source": "chat",
                "agent_type": payload.get("agent_type") or "unknown",
                "case_id": payload.get("case_id"),
                "context": "",
                "student_message": str(payload.get("user_message", "")),
                "tutor_response": str(payload.get("assistant_message", "")),
            })
        elif include_feedback and event_type == "formative_feedback_requested":
            items.append({
                "tutor_item_id": (
                    f"{payload.get('submission_id', 'unknown')}"
                    f":{payload.get('question_id', 'q?')}"
                    f":{payload.get('request_number', 0)}"
                ),
                "source": "formative_feedback",
                "agent_type": "formative_feedback",
                "case_id": payload.get("case_id"),
                "context": "",
                "student_message": str(payload.get("draft_text", "")),
                "tutor_response": str(payload.get("feedback", "")),
            })

    return [item for item in items if item["tutor_response"].strip()]


async def run_evaluation(items: list[dict], *, api_key: str, model: str | None = None) -> list[dict]:
    evaluator = TutorResponseEvaluator(api_key=api_key, model=model)

    async def annotate(item: dict) -> dict:
        annotation = await evaluator.evaluate_turn(
            context=item["context"],
            student_message=item["student_message"],
            tutor_response=item["tutor_response"],
        )
        return {**item, "annotation": annotation}

    return list(await asyncio.gather(*(annotate(item) for item in items)))


def write_results_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_results_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_summary(rows: list[dict], output_dir: Path, stamp: str) -> tuple[Path, Path]:
    summary = aggregate_annotations(rows)
    json_path = output_dir / f"tutor_eval_{stamp}_summary.json"
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    csv_path = output_dir / f"tutor_eval_{stamp}_summary.csv"
    lines = ["scope;dimension;desired_label;n_valid;desirability_rate;label_counts"]
    scopes = [("overall", summary["overall"])] + [
        (f"agent:{agent}", data) for agent, data in sorted(summary["by_agent_type"].items())
    ]
    for scope, data in scopes:
        for key, slot in data.items():
            counts = ", ".join(f"{label}={n}" for label, n in sorted(slot["counts"].items()))
            rate = slot["desirability_rate"]
            lines.append(
                f"{scope};{key};{slot['desired_label']};{slot['n_valid']};"
                f"{'' if rate is None else rate};{counts}"
            )
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, csv_path


def write_annotation_workbook(items: list[dict], path: Path) -> Path:
    """Blindes Workbook für menschliche Annotation (Validierung des Judge)."""
    from openpyxl import Workbook

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()

    sheet = workbook.active
    sheet.title = "annotation"
    dim_keys = list(TUTOR_EVAL_DIMENSIONS)
    sheet.append(
        ["tutor_item_id", "source", "agent_type", "student_message", "tutor_response"]
        + dim_keys
    )
    for item in items:
        sheet.append([
            item["tutor_item_id"], item["source"], item["agent_type"],
            item["student_message"], item["tutor_response"],
        ] + [None] * len(dim_keys))

    guide = workbook.create_sheet("labels")
    guide.append(["dimension", "definition", "allowed_labels", "desired_label"])
    for key, dim in TUTOR_EVAL_DIMENSIONS.items():
        guide.append([key, dim["definition"], " | ".join(dim["labels"]), dim["desired"]])

    workbook.save(path)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--limit", type=int, default=None, help="max. Anzahl Items")
    parser.add_argument("--agent-type", default=None, help="nur diesen Agent-Typ bewerten")
    parser.add_argument("--include-feedback", action="store_true",
                        help="auch formative Denkanstöße bewerten")
    parser.add_argument("--annotation-workbook", action="store_true",
                        help="nur blindes Human-Annotations-Workbook erzeugen (keine LLM-Calls)")
    parser.add_argument("--aggregate-only", type=Path, default=None,
                        help="vorhandene JSONL-Ergebnisse nur neu aggregieren")
    parser.add_argument("--model", default=None, help="Judge-Modell (Default: OPENROUTER_MODEL)")
    parser.add_argument("--dry-run", action="store_true", help="Items nur auflisten")
    args = parser.parse_args()

    stamp = _utc_stamp()

    if args.aggregate_only:
        rows = read_results_jsonl(args.aggregate_only)
        json_path, csv_path = write_summary(rows, args.output_dir, stamp)
        print(f"{len(rows)} Annotationen aggregiert -> {json_path} / {csv_path}")
        return 0

    events = json.loads(args.events.read_text(encoding="utf-8"))
    items = extract_tutor_items(events, include_feedback=args.include_feedback)
    if args.agent_type:
        items = [item for item in items if item["agent_type"] == args.agent_type]
    if args.limit:
        items = items[: args.limit]

    print(f"{len(items)} Tutor-Antworten aus {args.events}")

    if args.dry_run:
        for item in items[:20]:
            print(f"  {item['tutor_item_id']} [{item['agent_type']}] "
                  f"{item['tutor_response'][:80]!r}")
        if len(items) > 20:
            print(f"  … und {len(items) - 20} weitere")
        return 0

    if args.annotation_workbook:
        path = write_annotation_workbook(
            items, args.output_dir / f"tutor_annotation_{stamp}_blind.xlsx"
        )
        print(f"Annotations-Workbook -> {path}")
        return 0

    api_key = get_openrouter_key()
    if not api_key:
        print("FEHLER: OPENROUTER_API_KEY nicht konfiguriert.", file=sys.stderr)
        return 1

    print("Starte LLM-Judge (kostet API-Calls) …")
    rows = asyncio.run(run_evaluation(items, api_key=api_key, model=args.model))

    results_path = args.output_dir / f"tutor_eval_{stamp}.jsonl"
    write_results_jsonl(rows, results_path)
    json_path, csv_path = write_summary(rows, args.output_dir, stamp)

    invalid = sum(
        1 for row in rows
        for slot in row["annotation"].values()
        if slot["label"] == "Invalid"
    )
    print(f"Ergebnisse -> {results_path}")
    print(f"Aggregation -> {json_path} / {csv_path}")
    if invalid:
        print(f"HINWEIS: {invalid} ungültige Judge-Labels (siehe JSONL).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
