"""Smoke-Tests für das Backend-Skeleton (Phase 1)."""

import pytest
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
    assert "tp_phase" in data


def test_create_session():
    response = client.post("/sessions", json={"group_id": "group-01", "user_id": "user-42"})
    assert response.status_code == 201
    data = response.json()
    assert data["group_id"] == "group-01"
    assert data["tp_phase"] in [1, 2, 3, 4]
    assert "/ws/group-01/user-42" in data["websocket_url"]


def test_current_tp_phase_within_window():
    tp1_start = TP_SCHEDULE[1]["start"]
    assert current_tp_phase(tp1_start) == 1

    tp2_start = TP_SCHEDULE[2]["start"]
    assert current_tp_phase(tp2_start) == 2


def test_current_tp_phase_before_course():
    assert current_tp_phase(date(2026, 1, 1)) == 1


def test_current_tp_phase_after_course():
    assert current_tp_phase(date(2027, 1, 1)) == 4
