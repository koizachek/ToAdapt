"""Tests für die Gruppencode-Validierung gegen das Kurs-Schema (GROUP_CODE_MAX).

Ohne GROUP_CODE_MAX bleibt alles beim Alten (freie Selbstauskunft, auch für
Prolific-Läufe). Mit GROUP_CODE_MAX=n sind genau G1–Gn gültig — geprüft im
Login-Feedback (/auth/student/verify) und hart bei Session-/Submission-
Erstellung (Defense-in-Depth für direkte API-Aufrufe).
"""

import pytest
from fastapi.testclient import TestClient

from backend.anonymize import group_code_allowed, group_code_max
from backend.api import routes
from backend.main import app

GOLDEN_CASE = "alpes-bank-genai-001"


@pytest.fixture()
def client(monkeypatch):
    for var in ("MONGODB_URI", "MONGODB_MAS_NAME", "MONGODB_MAS_KEY", "MONGODB_HOST"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("STUDENT_ACCESS_CODE", raising=False)
    monkeypatch.setenv("PSEUDONYM_SECRET", "s3cret")
    routes._sessions.clear()
    routes._submissions.clear()
    return TestClient(app)


# ---------------------------------------------------------------------------
# Pure Validierung
# ---------------------------------------------------------------------------

def test_validation_off_by_default(monkeypatch):
    monkeypatch.delenv("GROUP_CODE_MAX", raising=False)
    assert group_code_max() == 0
    for code in ("G12", "G9999", "TEAMA", ""):
        assert group_code_allowed(code) is True


def test_validation_boundaries(monkeypatch):
    monkeypatch.setenv("GROUP_CODE_MAX", "360")
    assert group_code_allowed("G1") is True
    assert group_code_allowed("G360") is True
    assert group_code_allowed("G361") is False
    assert group_code_allowed("G0") is False
    assert group_code_allowed("TEAMA") is False
    # Leer = keine Gruppe (z.B. Prolific) — Pflichtfeld regelt der Login-Flow
    assert group_code_allowed("") is True


def test_invalid_max_value_disables_validation(monkeypatch):
    monkeypatch.setenv("GROUP_CODE_MAX", "kaputt")
    assert group_code_max() == 0
    assert group_code_allowed("TEAMA") is True


# ---------------------------------------------------------------------------
# Login-Feedback (/auth/student/verify)
# ---------------------------------------------------------------------------

def test_verify_without_body_stays_backward_compatible(client):
    res = client.post("/auth/student/verify")
    assert res.status_code == 200
    assert res.json() == {"ok": True, "required": False}


def test_verify_reports_group_validity_and_normalization(client, monkeypatch):
    monkeypatch.setenv("GROUP_CODE_MAX", "360")

    ok = client.post("/auth/student/verify", json={"group_code": " g12 "}).json()
    assert ok["group_code"] == "G12"
    assert ok["group_code_valid"] is True
    assert ok["group_code_max"] == 360

    bad = client.post("/auth/student/verify", json={"group_code": "520"}).json()
    assert bad["group_code"] == "G520"
    assert bad["group_code_valid"] is False


def test_verify_accepts_anything_when_validation_off(client, monkeypatch):
    monkeypatch.delenv("GROUP_CODE_MAX", raising=False)
    res = client.post("/auth/student/verify", json={"group_code": "Team A"}).json()
    assert res["group_code_valid"] is True
    assert res["group_code_max"] is None


# ---------------------------------------------------------------------------
# Defense-in-Depth: Session-/Submission-Erstellung
# ---------------------------------------------------------------------------

def test_session_rejects_invalid_group_when_enabled(client, monkeypatch):
    monkeypatch.setenv("GROUP_CODE_MAX", "360")
    res = client.post("/sessions", json={
        "user_id": "u1", "group_code": "G520", "case_id": GOLDEN_CASE,
    })
    assert res.status_code == 422
    assert "G520" in res.json()["detail"]

    ok = client.post("/sessions", json={
        "user_id": "u1", "group_code": "12", "case_id": GOLDEN_CASE,
    })
    assert ok.status_code == 201


def test_submission_rejects_invalid_group_when_enabled(client, monkeypatch):
    monkeypatch.setenv("GROUP_CODE_MAX", "360")
    res = client.post("/submissions", json={
        "user_id": "u1", "matrikelnummer": "21-000-000",
        "group_code": "TEAMA", "case_id": GOLDEN_CASE, "target_tp": 1,
    })
    assert res.status_code == 422


def test_creation_unchanged_when_validation_off(client, monkeypatch):
    monkeypatch.delenv("GROUP_CODE_MAX", raising=False)
    res = client.post("/sessions", json={
        "user_id": "u1", "group_code": "Team A", "case_id": GOLDEN_CASE,
    })
    assert res.status_code == 201
