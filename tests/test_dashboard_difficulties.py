"""Tests für die Fehlerquellen-Sicht (/dashboard/difficulties)."""

import json

import pytest
from fastapi.testclient import TestClient

import backend.db.dashboard_store as dashboard_store_module
from backend.main import app

API_KEY = "test-admin-key"


def _score(awarded: float, max_points: float, *, bloom: int, tags: list[str],
           penalties: list[str] | None = None, missing_blocks: list[str] | None = None,
           needs_review: bool = False) -> dict:
    return {
        "question_id": "q1",
        "bloom_level": bloom,
        "max_points": max_points,
        "awarded_points": awarded,
        "feedback": "…",
        "learning_objective_tags": tags,
        "main_penalties": penalties or [],
        "missing_canvas_blocks": missing_blocks or [],
        "needs_human_review": needs_review,
        "evaluation_status": "ok",
    }


def _result(matrikel: str, pct: float, scores: list[dict], tp: int = 1) -> dict:
    return {
        "submission_id": f"sub-{matrikel}-{pct}",
        "matrikelnummer": matrikel,
        "case_id": "case-1",
        "target_tp": tp,
        "percentage": pct,
        "evaluated_at": "2026-07-01T10:00:00",
        "scores": scores,
    }


@pytest.fixture()
def client(monkeypatch, tmp_path):
    for var in ("MONGODB_URI", "MONGODB_MAS_NAME", "MONGODB_MAS_KEY", "MONGODB_HOST"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("TOADAPT_API_KEY", API_KEY)
    monkeypatch.setattr(dashboard_store_module, "RESULTS_DIR", tmp_path)

    results = [
        # Schwacher Studierender: niedrige Scores, wiederkehrende Schwäche
        _result("1001", 38.0, [
            _score(2, 8, bloom=4, tags=["wirkungskette"],
                   penalties=["Keine Begründung der Priorisierung"],
                   missing_blocks=["revenue_streams"]),
            _score(3, 9, bloom=2, tags=["analyse"],
                   penalties=["Keine Begründung der Priorisierung"]),
        ]),
        _result("1001", 42.0, [
            _score(3, 8, bloom=4, tags=["wirkungskette"],
                   penalties=["keine Begründung der Priorisierung."],
                   missing_blocks=["revenue_streams"], needs_review=True),
        ]),
        # Starker Studierender
        _result("2002", 85.0, [
            _score(7, 8, bloom=4, tags=["wirkungskette"]),
            _score(8, 9, bloom=2, tags=["analyse"]),
        ]),
    ]
    for i, r in enumerate(results):
        (tmp_path / f"r{i}.json").write_text(json.dumps(r), encoding="utf-8")

    return TestClient(app)


def test_difficulties_requires_api_key(client):
    assert client.get("/dashboard/difficulties").status_code == 401


def test_difficulties_prioritizes_struggling_student(client):
    res = client.get("/dashboard/difficulties", headers={"X-API-Key": API_KEY})
    assert res.status_code == 200
    data = res.json()

    assert data["threshold_pct"] == 60.0
    # Schwacher Studierender zuerst, mit high attention
    first = data["students"][0]
    assert first["matrikelnummer"] == "1001"
    assert first["attention_level"] == "high"
    assert "low_avg" in first["attention_reasons"]
    assert first["needs_human_review_count"] == 1

    # Schwache Lernziele erkannt
    weak_tags = {o["tag"] for o in first["weak_objectives"]}
    assert "wirkungskette" in weak_tags and "analyse" in weak_tags

    # Wiederkehrende Schwäche case-insensitiv und ohne Satzzeichen aggregiert:
    # alle 3 Nennungen landen in einer Gruppe
    penalties = first["recurring_penalties"]
    assert penalties[0]["count"] == 3
    assert penalties[0]["text"].casefold() == "keine begründung der priorisierung"
    assert first["missing_canvas_blocks"][0]["text"] == "revenue_streams"

    # Starker Studierender: low attention, keine schwachen Lernziele
    strong = next(s for s in data["students"] if s["matrikelnummer"] == "2002")
    assert strong["attention_level"] == "low"
    assert strong["weak_objectives"] == []


def test_difficulties_cohort_aggregation(client):
    data = client.get("/dashboard/difficulties", headers={"X-API-Key": API_KEY}).json()

    by_tag = {o["tag"]: o for o in data["cohort_weak_objectives"]}
    assert by_tag["wirkungskette"]["students_total"] == 2
    assert by_tag["wirkungskette"]["students_below"] == 1

    assert data["cohort_common_penalties"][0]["count"] >= 2
