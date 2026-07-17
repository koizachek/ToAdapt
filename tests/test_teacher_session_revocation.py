"""Tests für den serverseitigen Teacher-Session-Widerruf (Logout-Härtung).

Der Teacher-Proxy schickt die jti der verifizierten Session als
X-Teacher-Session mit; nach POST /auth/teacher-session/revoke muss jeder
Request mit dieser jti auf den proxy-erreichbaren Routern (dashboard, admin,
group-uploads) mit 401 abgewiesen werden. Requests ohne Header (Forschende,
Skripte, Alt-Sessions ohne jti) bleiben unberührt.
"""

import pytest
from fastapi.testclient import TestClient

from backend.db.revoked_sessions_store import RevokedSessionStore, revoked_session_store
from backend.main import app

API_KEY = "test-admin-key"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("TOADAPT_API_KEY", API_KEY)
    # Frische Sperrliste pro Test (Singleton hält sonst jtis über Tests hinweg).
    monkeypatch.setattr(revoked_session_store, "_memory", {})
    return TestClient(app)


def test_revoke_endpoint_fail_closed_without_key(client, monkeypatch):
    monkeypatch.delenv("TOADAPT_API_KEY", raising=False)
    res = client.post("/auth/teacher-session/revoke", json={"jti": "jti-fail-closed"})
    assert res.status_code == 503


def test_revoke_endpoint_rejects_wrong_key(client):
    res = client.post(
        "/auth/teacher-session/revoke",
        json={"jti": "jti-wrong-key"},
        headers={"X-API-Key": "falsch"},
    )
    assert res.status_code == 401


def test_revoked_session_gets_401_on_dashboard(client):
    jti = "jti-revoked-001"
    res = client.post(
        "/auth/teacher-session/revoke", json={"jti": jti}, headers={"X-API-Key": API_KEY}
    )
    assert res.status_code == 200
    assert res.json()["revoked"] is True
    # Ohne Mongo (conftest-Isolation) greift das In-Memory-Fallback.
    assert res.json()["persisted"] is False

    blocked = client.get(
        "/dashboard/overview",
        headers={"X-API-Key": API_KEY, "X-Teacher-Session": jti},
    )
    assert blocked.status_code == 401
    assert "abgemeldet" in blocked.json()["detail"]


def test_active_session_and_headerless_requests_pass(client):
    ok = client.get(
        "/dashboard/overview",
        headers={"X-API-Key": API_KEY, "X-Teacher-Session": "jti-aktiv-002"},
    )
    assert ok.status_code == 200

    # Forschende/Skripte ohne Header: unberührt.
    no_header = client.get("/dashboard/overview", headers={"X-API-Key": API_KEY})
    assert no_header.status_code == 200


def test_revoked_session_blocked_on_admin_router(client):
    jti = "jti-revoked-admin"
    client.post("/auth/teacher-session/revoke", json={"jti": jti}, headers={"X-API-Key": API_KEY})

    blocked = client.get("/admin/cases", headers={"X-Teacher-Session": jti})
    assert blocked.status_code == 401
    # Lesende /admin/cases ohne Header bleiben öffentlich (Studierenden-Frontend).
    assert client.get("/admin/cases").status_code == 200


def test_store_memory_fallback_and_unknown_jti():
    store = RevokedSessionStore()
    assert store.is_revoked("nie-gesehen") is False
    persisted = store.revoke("jti-memory-003")
    assert persisted is False  # kein Mongo in Tests
    assert store.is_revoked("jti-memory-003") is True


def test_revoke_validates_jti_length(client):
    res = client.post(
        "/auth/teacher-session/revoke", json={"jti": "kurz"}, headers={"X-API-Key": API_KEY}
    )
    assert res.status_code == 422
