"""Konten der Übungsgruppenleiter (UEGL01–UEGL26): Passwort selbst festlegen,
Login, Passwort vergessen → Master-Einmalcode → neues Passwort.

Store-Ebene (Hash/Verify, Policy, Reset-Ablauf) und Routen (/auth/tutor/*,
fail-closed hinter X-API-Key, Master-Gate für Einmalcode + Kontoliste).
Keine echten Daten — Konten sind synthetisch, Passwörter Testwerte.
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

import backend.db.tutor_account_store as store_module
from backend.config.tutor_accounts import TUTOR_ACCOUNTS, normalize_account
from backend.db.tutor_account_store import (
    PasswordPolicyError,
    TutorAccountStore,
    hash_secret,
    verify_secret,
)
from backend.main import app
from backend.timeutils import naive_utcnow

API_KEY = "test-api-key-1234567890"


@pytest.fixture()
def store(monkeypatch, tmp_path):
    monkeypatch.setattr(store_module, "ACCOUNTS_DIR", tmp_path)
    monkeypatch.setattr(store_module, "PBKDF2_ITERATIONS", 1_000)   # Tests schnell halten
    return TutorAccountStore()


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("TOADAPT_API_KEY", API_KEY)
    monkeypatch.setattr(store_module, "ACCOUNTS_DIR", tmp_path)
    monkeypatch.setattr(store_module, "PBKDF2_ITERATIONS", 1_000)
    return TestClient(app)


def _key() -> dict:
    return {"X-API-Key": API_KEY}


def _master() -> dict:
    return {"X-API-Key": API_KEY, "X-Teacher-Id": "master", "X-Teacher-Master": "1"}


def _tutor(account: str) -> dict:
    return {"X-API-Key": API_KEY, "X-Teacher-Id": account, "X-Teacher-Master": "0"}


# ---------------------------------------------------------------------------
# Config + Hashing
# ---------------------------------------------------------------------------

def test_accounts_and_normalization():
    assert len(TUTOR_ACCOUNTS) == 27 and TUTOR_ACCOUNTS[:2] == ("UEGL00", "UEGL01") and TUTOR_ACCOUNTS[-1] == "UEGL26"
    assert normalize_account("uegl0") == "UEGL00"
    assert normalize_account("uegl5") == "UEGL05" and normalize_account(" UEGL 26 ") == "UEGL26"
    assert normalize_account("UEGL27") == "" and normalize_account("UEG07") == "" and normalize_account("") == ""


def test_hash_and_verify_never_store_plaintext(monkeypatch):
    monkeypatch.setattr(store_module, "PBKDF2_ITERATIONS", 1_000)
    stored = hash_secret("geheim1")
    assert "geheim1" not in stored and stored.startswith("pbkdf2_sha256$")
    assert verify_secret("geheim1", stored) is True
    assert verify_secret("geheim2", stored) is False
    assert verify_secret("geheim1", None) is False and verify_secret("x", "kaputt") is False
    assert hash_secret("geheim1") != stored          # zufälliges Salt


# ---------------------------------------------------------------------------
# Store-Ablauf
# ---------------------------------------------------------------------------

def test_first_login_sets_password_then_verifies(store):
    assert store.verify("UEGL05", "irgendwas") == "set_password"
    with pytest.raises(PasswordPolicyError):
        store.set_password("UEGL05", "12345")           # unter 6 Zeichen
    assert store.set_password("UEGL05", "sechs6") is True
    assert store.set_password("UEGL05", "anders7") is False   # existiert schon → kein Überschreiben
    assert store.verify("UEGL05", "sechs6") == "ok"
    assert store.verify("UEGL05", "falsch") == "wrong"
    assert store.verify("UEGL99", "x") == "unknown"
    view = store.public_view(store.get("UEGL05"))
    assert view["password_set"] is True and "password_hash" not in view
    assert store.get("UEGL05")["last_login_at"] is not None
    # Kein Klartext auf der Platte
    raw = (store_module.ACCOUNTS_DIR / "UEGL05.json").read_text(encoding="utf-8")
    assert "sechs6" not in raw


def test_reset_request_code_and_consume(store):
    store.set_password("UEGL03", "start123")
    assert store.request_reset("UEGL03") is True
    assert store.public_view(store.get("UEGL03"))["reset_requested_at"] is not None
    code, expires = store.issue_reset_code("UEGL03", issued_by="master")
    assert len(code) == 14 and "-" in code
    view = store.public_view(store.get("UEGL03"))
    assert view["reset_code_active"] is True and view["reset_code_expires_at"] == expires
    # Altes Passwort gilt weiter, bis der Code eingelöst wird
    assert store.verify("UEGL03", "start123") == "ok"
    # Falscher Code = falsches Passwort
    assert store.verify("UEGL03", "aaaa-bbbb-cccc") == "wrong"
    # Code einlösen → altes Passwort weg, neues festlegen
    assert store.verify("UEGL03", code) == "reset_code"
    assert store.verify("UEGL03", "start123") == "set_password"
    assert store.verify("UEGL03", code) == "set_password"     # einmalig
    assert store.set_password("UEGL03", "neu-456") is True
    assert store.verify("UEGL03", "neu-456") == "ok"
    view = store.public_view(store.get("UEGL03"))
    assert view["reset_requested_at"] is None and view["reset_code_active"] is False


def test_expired_reset_code_is_ignored(store):
    store.set_password("UEGL04", "start123")
    code, _ = store.issue_reset_code("UEGL04", issued_by=None)
    record = store.get("UEGL04")
    record["reset_code_expires_at"] = (naive_utcnow() - timedelta(minutes=1)).isoformat()
    store._save(record)
    assert store.verify("UEGL04", code) == "wrong"
    assert store.public_view(store.get("UEGL04"))["reset_code_active"] is False


def test_list_all_covers_every_account(store):
    rows = store.list_all()
    assert [r["account"] for r in rows] == list(TUTOR_ACCOUNTS)
    assert all(r["password_hash"] is None for r in rows)


# ---------------------------------------------------------------------------
# Routen
# ---------------------------------------------------------------------------

def test_routes_fail_closed(client, monkeypatch):
    monkeypatch.delenv("TOADAPT_API_KEY")
    assert client.post("/auth/tutor/login", json={"account": "UEGL01", "password": "x"}).status_code == 503
    monkeypatch.setenv("TOADAPT_API_KEY", API_KEY)
    assert client.post("/auth/tutor/login", json={"account": "UEGL01", "password": "x"},
                       headers={"X-API-Key": "falsch"}).status_code == 401


def test_login_set_password_and_wrong_password(client):
    # Unbekanntes Konto
    assert client.post("/auth/tutor/login", json={"account": "UEG07", "password": "x"}, headers=_key()).status_code == 404
    # Erster Login: Konto ohne Passwort → set_password (nichts wird gesetzt)
    r = client.post("/auth/tutor/login", json={"account": "uegl2", "password": "egal"}, headers=_key())
    assert r.status_code == 200 and r.json() == {"status": "set_password", "account": "UEGL02", "reason": "first_login"}
    # Passwort zu kurz → 422 mit Klartext-Hinweis
    r = client.post("/auth/tutor/set-password", json={"account": "UEGL02", "password": "kurz"}, headers=_key())
    assert r.status_code == 422 and "mindestens 6" in r.json()["detail"]
    r = client.post("/auth/tutor/set-password", json={"account": "UEGL02", "password": "sicher"}, headers=_key())
    assert r.status_code == 200 and r.json()["status"] == "ok"
    # Zweites Setzen → 409
    assert client.post("/auth/tutor/set-password", json={"account": "UEGL02", "password": "anders"}, headers=_key()).status_code == 409
    # Login
    assert client.post("/auth/tutor/login", json={"account": "UEGL02", "password": "sicher"}, headers=_key()).json()["status"] == "ok"
    assert client.post("/auth/tutor/login", json={"account": "UEGL02", "password": "falsch"}, headers=_key()).status_code == 401


def test_reset_flow_via_routes_and_master_gate(client):
    client.post("/auth/tutor/set-password", json={"account": "UEGL09", "password": "start1"}, headers=_key())
    # Anfrage (öffentlich über das Frontend, mit API-Key) → im Kontostatus sichtbar
    assert client.post("/auth/tutor/reset-request", json={"account": "UEGL09"}, headers=_key()).json()["status"] == "requested"
    assert client.get("/auth/tutor/accounts", headers=_tutor("UEGL09")).status_code == 403
    accounts = client.get("/auth/tutor/accounts", headers=_master()).json()
    row = next(a for a in accounts if a["account"] == "UEGL09")
    assert row["reset_requested_at"] is not None and row["password_set"] is True
    assert all("password_hash" not in a and "reset_code_hash" not in a for a in accounts)
    # Einmalcode nur Master
    assert client.post("/auth/tutor/UEGL09/reset-code", headers=_tutor("UEGL09")).status_code == 403
    assert client.post("/auth/tutor/UEGL99/reset-code", headers=_master()).status_code == 404
    issued = client.post("/auth/tutor/UEGL09/reset-code", headers=_master()).json()
    assert issued["account"] == "UEGL09" and issued["code"] and issued["expires_at"]
    # Operator (Skript ohne Identitäts-Header) darf ebenfalls
    assert client.post("/auth/tutor/UEGL09/reset-code", headers=_key()).status_code == 200
    # Einlösen: Login mit dem Code → set_password, dann neues Passwort
    code = client.post("/auth/tutor/UEGL09/reset-code", headers=_master()).json()["code"]
    r = client.post("/auth/tutor/login", json={"account": "UEGL09", "password": code}, headers=_key())
    assert r.json() == {"status": "set_password", "account": "UEGL09", "reason": "reset_code"}
    assert client.post("/auth/tutor/set-password", json={"account": "UEGL09", "password": "neu-pw"}, headers=_key()).status_code == 200
    assert client.post("/auth/tutor/login", json={"account": "UEGL09", "password": "neu-pw"}, headers=_key()).json()["status"] == "ok"
    assert client.post("/auth/tutor/login", json={"account": "UEGL09", "password": "start1"}, headers=_key()).status_code == 401
    row = next(a for a in client.get("/auth/tutor/accounts", headers=_master()).json() if a["account"] == "UEGL09")
    assert row["reset_requested_at"] is None and row["reset_code_active"] is False
