from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "publish_dashboard_scores.py"
SPEC = importlib.util.spec_from_file_location("publish_dashboard_scores", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_publish_dashboard_scores_writes_only_evaluated_scores(tmp_path):
    source_path = tmp_path / "submission_states.json"
    output_dir = tmp_path / "dashboard"
    source_path.write_text(
        json.dumps(
            [
                {
                    "submission_id": "sub-1",
                    "user_id": "user-1",
                    "matrikelnummer": "pid-1",
                    "case_id": "case-alpha",
                    "target_tp": 1,
                    "status": "evaluated",
                    "percentage": 72.5,
                    "canvas_alignment_pct": 60.0,
                    "rubric_fit_pct": 68.0,
                    "canvas_exemplar_candidate": False,
                    "submitted_at": "2026-05-31T12:00:00",
                    "evaluated_at": "2026-05-31T12:01:00",
                    "scores": [
                        {
                            "question_id": "q1",
                            "bloom_level": 4,
                            "max_points": 25,
                            "awarded_points": 18,
                            "needs_human_review": True,
                            "evaluation_status": "ok",
                        },
                        {
                            "question_id": "q2",
                            "bloom_level": 5,
                            "max_points": 24,
                            "awarded_points": 0,
                            "needs_human_review": True,
                            "evaluation_status": "technical_fallback",
                        },
                    ],
                    "experiment": {"prolific_pid": "pid-1"},
                },
                {
                    "submission_id": "sub-empty",
                    "status": "skipped_no_answers",
                    "scores": [],
                },
            ]
        ),
        encoding="utf-8",
    )

    summary = MODULE.publish_dashboard_scores(source_path, output_dir)

    assert summary.published == 1
    assert summary.skipped == 1
    assert summary.needs_human_review_count == 2
    assert summary.technical_fallback_count == 1

    written = json.loads((output_dir / "sub-1.json").read_text(encoding="utf-8"))
    assert written["matrikelnummer"] == "pid-1"
    assert written["percentage"] == 72.5
    assert written["scores"][1]["evaluation_status"] == "technical_fallback"
    assert not (output_dir / "sub-empty.json").exists()
