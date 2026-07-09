#!/usr/bin/env python3
"""Lernziel-Trajektorien pro Lerner:in aus Dashboard-Ergebnissen (deskriptiv).

Erste Stufe von Knowledge Tracing in ToAdapt: chronologische Leistungsreihen
pro (Pseudonym × Lernziel-Tag) mit EWMA-Mastery-Schätzung und Delta
erste→letzte Messung. KEINE LLM-Calls, rein deskriptiv.

Input:  Verzeichnis mit Dashboard-Ergebnis-JSONs (eine Datei pro Submission,
        wie backend/db/submissions/ bzw. ein Mongo-Export der Collection
        dashboard_results als Einzeldateien).
Output: CSV (Semikolon): learner;group;tag;n;first_pct;last_pct;delta;ewma_mastery

Aufruf:
    python objective_trajectories.py <results_dir> [--out trajektorien.csv] [--alpha 0.4]

ACHTUNG: Arbeitet mit pseudonymisierten Einzeldaten → Forschungs-Kontext,
Ergebnis-CSV NICHT an Tutor:innen geben (nur Gruppen-Aggregate erlaubt).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def load_results(results_dir: Path) -> list[dict]:
    results = []
    for path in sorted(results_dir.glob("*.json")):
        try:
            results.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:
            print(f"WARN: {path.name} unlesbar ({exc})", file=sys.stderr)
    return results


def build_trajectories(results: list[dict]) -> dict[tuple[str, str, str], list[tuple[str, float]]]:
    """(learner, group, tag) → chronologische Liste (evaluated_at, pct)."""
    series: dict[tuple[str, str, str], list[tuple[str, float]]] = defaultdict(list)
    for result in results:
        learner = str(result.get("matrikelnummer", "")) or "unbekannt"
        group = str(result.get("group_code", "")) or "OHNE-GRUPPE"
        when = str(result.get("evaluated_at") or result.get("submitted_at") or "")
        for score in result.get("scores", []):
            max_points = score.get("max_points") or 0
            if not max_points:
                continue
            pct = round(score.get("awarded_points", 0) / max_points * 100, 1)
            for tag in score.get("learning_objective_tags", []):
                series[(learner, group, str(tag))].append((when, pct))
    for key in series:
        series[key].sort(key=lambda item: item[0])
    return series


def ewma(values: list[float], alpha: float) -> float:
    """Exponentiell gewichteter Schnitt — jüngste Messungen zählen stärker."""
    estimate = values[0]
    for value in values[1:]:
        estimate = alpha * value + (1 - alpha) * estimate
    return round(estimate, 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results_dir", type=Path)
    parser.add_argument("--out", type=Path, default=Path("objective_trajectories.csv"))
    parser.add_argument("--alpha", type=float, default=0.4,
                        help="EWMA-Gewicht der jüngsten Messung (0..1, Default 0.4)")
    args = parser.parse_args()

    results = load_results(args.results_dir)
    if not results:
        print("Keine Ergebnis-JSONs gefunden.", file=sys.stderr)
        return 1

    series = build_trajectories(results)
    lines = ["learner;group;tag;n;first_pct;last_pct;delta;ewma_mastery"]
    for (learner, group, tag), points in sorted(series.items()):
        pcts = [pct for _, pct in points]
        lines.append(
            f"{learner};{group};{tag};{len(pcts)};{pcts[0]};{pcts[-1]};"
            f"{round(pcts[-1] - pcts[0], 1)};{ewma(pcts, args.alpha)}"
        )
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(series)} Trajektorien aus {len(results)} Submissions -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
