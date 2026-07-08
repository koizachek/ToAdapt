"""Smoke-Tests für das Backend-Skeleton (Phase 1)."""

from fastapi.testclient import TestClient

from backend.main import app
from backend.config.tp_configs import current_tp_phase, TP_SCHEDULE
from datetime import date


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    # /health ist bewusst minimal — Infrastruktur-Details liegen unter
    # /health/diagnostics (API-Key-geschützt).
    assert "mongo_env_keys" not in data


def test_health_diagnostics_requires_key():
    # Ohne konfigurierten/übergebenen Key: fail-closed.
    assert client.get("/health/diagnostics").status_code in (401, 503)


def test_dashboard_requires_key():
    assert client.get("/dashboard/overview").status_code in (401, 503)


def test_create_session():
    response = client.post(
        "/sessions",
        json={
            "user_id": "user-42",
            "case_id": "alpes-bank-genai-001",
            "experiment": {
                "prolific_pid": "pid-123",
                "prolific_study_id": "study-456",
                "prolific_session_id": "session-789",
            },
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == "user-42"
    assert data["case_id"] == "alpes-bank-genai-001"
    assert data["tp_phase"] in [1, 2, 3, 4]
    assert data["websocket_url"].startswith("/ws/")


def test_current_tp_phase_within_window():
    tp1_start = TP_SCHEDULE[1]["start"]
    assert current_tp_phase(tp1_start) == 1

    tp2_start = TP_SCHEDULE[2]["start"]
    assert current_tp_phase(tp2_start) == 2


def test_current_tp_phase_before_course():
    assert current_tp_phase(date(2026, 1, 1)) == 1


def test_current_tp_phase_after_course():
    assert current_tp_phase(date(2027, 1, 1)) == 4
