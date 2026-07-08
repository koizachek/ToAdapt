#!/usr/bin/env python3
"""Fasst ToAdapt-Dashboard-Result-JSONs zusammen — ohne Mongo lauffähig.

Input (ein oder mehrere Pfade):
  - Verzeichnis mit einzelnen Result-JSONs (Datei-Fallback des Backends:
    backend/db/submissions/ — eine Datei pro Submission), und/oder
  - einzelne JSON-Datei, die entweder EIN Result-Objekt oder eine LISTE von
    Result-Objekten enthält (z.B. ein Mongo-Export der Collection
    dashboard_results via `mongoexport --jsonArray`).

Erwartetes Result-Schema (geschrieben von POST /submissions/{id}/submit in
backend/api/routes.py): submission_id, matrikelnummer, case_id, target_tp,
percentage, canvas_alignment_pct, rubric_fit_pct, canvas_exemplar_candidate,
submitted_at, evaluated_at, scores[] (QuestionScore-Dumps mit question_id,
awarded_points, max_points, needs_human_review, evaluation_status, ...).

Ausgabe: Anzahl Submissions, Ø-Scores, needs_human_review-Quote und
technical_fallback-Quote (gesamt und pro question_id). Nur Standardbibliothek,
keine Schreibzugriffe.

Usage:
  python3 summarize_dashboard_results.py backend/db/submissions/
  python3 summarize_dashboard_results.py export.json
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def _load_results(paths: list[str]) -> list[dict]:
    results: list[dict] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files = sorted(p.glob("*.json"))
        elif p.is_file():
            files = [p]
        else:
            print(f"WARN: Pfad nicht gefunden, übersprungen: {p}", file=sys.stderr)
            continue
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception as exc:
                print(f"WARN: {f} nicht lesbar ({exc}), übersprungen", file=sys.stderr)
                continue
            if isinstance(data, list):
                results.extend(d for d in data if isinstance(d, dict))
            elif isinstance(data, dict):
                results.append(data)
    return results


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    results = _load_results(sys.argv[1:])
    if not results:
        print("Keine Results gefunden.")
        return 1

    pct = [float(r.get("percentage", 0.0)) for r in results]
    canvas = [float(r.get("canvas_alignment_pct", 0.0)) for r in results]
    fit = [float(r.get("rubric_fit_pct", 0.0)) for r in results]
    exemplar = sum(1 for r in results if r.get("canvas_exemplar_candidate"))
    cases = sorted({str(r.get("case_id", "?")) for r in results})

    # Frage-Ebene: eine Zeile pro QuestionScore
    all_scores: list[dict] = []
    for r in results:
        for s in r.get("scores", []) or []:
            if isinstance(s, dict):
                all_scores.append(s)

    review_flags = sum(1 for s in all_scores if s.get("needs_human_review"))
    tech_fallback = sum(
        1 for s in all_scores if s.get("evaluation_status") == "technical_fallback"
    )

    print("== ToAdapt Dashboard-Results — Zusammenfassung ==")
    print(f"Submissions:                  {len(results)}")
    print(f"Cases:                        {len(cases)} ({', '.join(cases[:8])}{'…' if len(cases) > 8 else ''})")
    print(f"Ø percentage:                 {_mean(pct):.1f} %")
    print(f"Ø canvas_alignment_pct:       {_mean(canvas):.1f} %")
    print(f"Ø rubric_fit_pct:             {_mean(fit):.1f} %")
    print(f"canvas_exemplar_candidate:    {exemplar}/{len(results)}")
    print(f"Frage-Scores gesamt:          {len(all_scores)}")
    if all_scores:
        print(
            f"needs_human_review-Quote:     {review_flags}/{len(all_scores)}"
            f" ({review_flags / len(all_scores) * 100:.1f} % der Frage-Scores)"
        )
        print(
            f"technical_fallback-Quote:     {tech_fallback}/{len(all_scores)}"
            f" ({tech_fallback / len(all_scores) * 100:.1f} % der Frage-Scores)"
        )

    # Pro question_id
    by_q: dict[str, list[dict]] = defaultdict(list)
    for s in all_scores:
        by_q[str(s.get("question_id", "?"))].append(s)

    if by_q:
        print("\n-- Pro Frage --")
        print(f"{'question_id':<14}{'n':>4}{'Ø awarded':>11}{'Ø max':>8}{'Ø %':>8}{'review':>8}{'tech_fb':>9}")
        for qid in sorted(by_q):
            rows = by_q[qid]
            awarded = _mean([float(s.get("awarded_points", 0.0)) for s in rows])
            maxp = _mean([float(s.get("max_points", 0.0)) for s in rows])
            q_pct = (awarded / maxp * 100) if maxp else 0.0
            rev = sum(1 for s in rows if s.get("needs_human_review"))
            tfb = sum(1 for s in rows if s.get("evaluation_status") == "technical_fallback")
            print(f"{qid:<14}{len(rows):>4}{awarded:>11.2f}{maxp:>8.1f}{q_pct:>7.1f}%{rev:>8}{tfb:>9}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
