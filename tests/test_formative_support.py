"""Tests für Live-Unterstützung in der Fragen-Section: Coverage, Denkanstoß, Tipp-Telemetrie."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import routes
from backend.dashboard.routes import _count_paste_heavy
from backend.main import app

GOLDEN_CASE = "alpes-bank-genai-001"


@pytest.fixture()
def client(monkeypatch):
    for var in ("MONGODB_URI", "MONGODB_MAS_NAME", "MONGODB_MAS_KEY", "MONGODB_HOST"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("STUDENT_ACCESS_CODE", raising=False)
    routes._submissions.clear()
    return TestClient(app)


def _create_submission(client) -> str:
    res = client.post("/submissions", json={
        "user_id": "u-test", "matrikelnummer": "test-9999",
        "case_id": GOLDEN_CASE, "target_tp": 1,
    })
    assert res.status_code == 201
    return res.json()["submission_id"]


def _tp1_q1_keyword() -> tuple[str, str]:
    """Liefert (block, ein accepted_keyword) aus der echten tp1-Rubric für q1."""
    rubric = json.loads(
        (Path("backend/config/rubrics/tp1_rubric.json")).read_text(encoding="utf-8")
    )
    q = rubric["questions"].get("q1") or rubric.get("default")
    block = q["required_canvas_blocks"][0]
    return block["block"], block["accepted_keywords"][0]


# ---------------------------------------------------------------------------
# Coverage (deterministisch, kein LLM)
# ---------------------------------------------------------------------------

def test_coverage_marks_addressed_blocks(client):
    sub_id = _create_submission(client)
    block, keyword = _tp1_q1_keyword()

    res = client.post(
        f"/submissions/{sub_id}/questions/q1/coverage",
        json={"answer_text": f"Unser Entwurf behandelt {keyword} ausführlich."},
    )
    assert res.status_code == 200
    blocks = {b["block"]: b for b in res.json()["blocks"]}
    assert blocks[block]["addressed"] is True
    # Keywords dürfen NIE in der Antwort auftauchen (Scoring-Signal-Leak)
    assert keyword not in json.dumps(res.json())

    res_empty = client.post(
        f"/submissions/{sub_id}/questions/q1/coverage",
        json={"answer_text": "xyz ohne relevante Begriffe"},
    )
    assert all(b["addressed"] is False for b in res_empty.json()["blocks"])


def test_coverage_unknown_question_404(client):
    sub_id = _create_submission(client)
    res = client.post(
        f"/submissions/{sub_id}/questions/gibt-es-nicht/coverage",
        json={"answer_text": "x"},
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Denkanstoß (formatives Feedback, limitiert)
# ---------------------------------------------------------------------------

def _mock_llm(monkeypatch, reply: str):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    async def fake_complete(self, *, system, messages, max_tokens):
        return reply

    monkeypatch.setattr("backend.llm.OpenRouterClient.complete", fake_complete)


def test_feedback_limited_to_two_per_question(client, monkeypatch):
    _mock_llm(monkeypatch, "Woran würdest du erkennen, dass deine Entscheidung trägt?")
    sub_id = _create_submission(client)
    draft = {"answer_text": "Die Bank sollte den Chatbot einführen, weil es modern ist."}

    first = client.post(f"/submissions/{sub_id}/questions/q1/feedback", json=draft)
    assert first.status_code == 200
    assert first.json()["remaining"] == 1
    assert "Woran" in first.json()["feedback"]

    second = client.post(f"/submissions/{sub_id}/questions/q1/feedback", json=draft)
    assert second.json()["remaining"] == 0

    third = client.post(f"/submissions/{sub_id}/questions/q1/feedback", json=draft)
    assert third.status_code == 429

    # Andere Frage hat eigenes Kontingent
    other = client.post(f"/submissions/{sub_id}/questions/q2/feedback", json=draft)
    assert other.status_code == 200


def test_feedback_guardrail_replaces_forbidden_output(client, monkeypatch):
    _mock_llm(monkeypatch, "Nutzt hier am besten Porter und die Five Forces.")
    sub_id = _create_submission(client)

    res = client.post(
        f"/submissions/{sub_id}/questions/q1/feedback",
        json={"answer_text": "Erster Entwurf mit einer These."},
    )
    assert res.status_code == 200
    feedback = res.json()["feedback"]
    assert "Porter" not in feedback and "Five Forces" not in feedback
    assert "?" in feedback  # Fallback ist eine sokratische Frage


def test_feedback_rejects_empty_draft(client, monkeypatch):
    _mock_llm(monkeypatch, "egal")
    sub_id = _create_submission(client)
    res = client.post(f"/submissions/{sub_id}/questions/q1/feedback", json={"answer_text": "   "})
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# Tipp-Telemetrie
# ---------------------------------------------------------------------------

def test_answer_stats_persisted(client):
    sub_id = _create_submission(client)
    res = client.post(f"/submissions/{sub_id}/answer", json={
        "question_id": "q1",
        "answer_text": "Meine Antwort.",
        "stats": {"typed_chars": 20, "pasted_chars": 500, "paste_count": 1,
                  "largest_paste": 500, "edit_seconds": 12.5},
    })
    assert res.status_code == 200
    stored = routes._submissions[sub_id]
    assert stored.answer_stats["q1"].pasted_chars == 500
    assert stored.answer_stats["q1"].paste_share > 0.9


def test_count_paste_heavy_thresholds():
    results = [{"answer_stats": {
        "q1": {"typed_chars": 100, "pasted_chars": 400},   # 80% + >=300 → zählt
        "q2": {"typed_chars": 500, "pasted_chars": 100},   # Anteil zu klein
        "q3": {"typed_chars": 10, "pasted_chars": 100},    # Anteil hoch, aber <300 chars
    }}]
    assert _count_paste_heavy(results) == 1
