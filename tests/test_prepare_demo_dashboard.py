"""Tests für die Demo-Daten-Sanitisierung (PII-Wächter, Pseudonyme, Gruppen)."""

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "prepare_demo_dashboard", REPO_ROOT / "scripts" / "prepare_demo_dashboard.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _result(pid: str, sub: str, pct: float) -> dict:
    return {
        "submission_id": sub, "matrikelnummer": pid, "case_id": "c1",
        "target_tp": 1, "percentage": pct,
        "experiment": {"provider": "prolific", "prolific_pid": pid},
        "scores": [{"question_id": "q1", "awarded_points": 5, "max_points": 10,
                    "bloom_level": 4, "learning_objective_tags": ["analyse"],
                    "feedback": "ok", "main_penalties": []}],
    }


def test_sanitize_removes_all_pii_and_assigns_groups():
    module = _load()
    pids = [f"63ba24aa00112233445566{i:02d}" for i in range(6)]
    results = [_result(pid, f"sub-{i}", 50 + i) for i, pid in enumerate(pids)]

    sanitized = module.sanitize_results(results, ["DEMO-G1", "DEMO-G2"])

    import json
    blob = json.dumps(sanitized)
    assert "prolific" not in blob.lower()
    assert not module.HEX24.search(blob)
    for pid in pids:
        assert pid not in blob

    ids = sorted({r["matrikelnummer"] for r in sanitized})
    assert ids == [f"demo-{i:03d}" for i in range(1, 7)]
    assert all(r["demo"] is True for r in sanitized)
    assert all(r["submission_id"].startswith("demo-") for r in sanitized)
    groups = {r["group_code"] for r in sanitized}
    assert groups == {"DEMO-G1", "DEMO-G2"}
    # Round-Robin: gleiche Person → gleiche Gruppe, Verteilung ausgeglichen
    from collections import Counter
    counts = Counter(r["group_code"] for r in sanitized)
    assert max(counts.values()) - min(counts.values()) <= 0


def test_sanitize_is_deterministic_per_person():
    module = _load()
    results = [_result("aaa", "s1", 40), _result("aaa", "s2", 60), _result("bbb", "s3", 70)]
    sanitized = module.sanitize_results(results, ["G1", "G2"])
    by_sub = {r["submission_id"]: r for r in sanitized}
    assert by_sub["demo-s1"]["matrikelnummer"] == by_sub["demo-s2"]["matrikelnummer"]
    assert by_sub["demo-s1"]["group_code"] == by_sub["demo-s2"]["group_code"]
    assert by_sub["demo-s3"]["matrikelnummer"] != by_sub["demo-s1"]["matrikelnummer"]


def test_guard_aborts_on_leftover_hex24():
    module = _load()
    with pytest.raises(SystemExit):
        module._guard_no_pii([{"note": "63ba24aa0011223344556699"}], set())
