"""Tests für Gruppen-Aggregate, Pseudonymisierung und Forschungs-Key-Gating."""

import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import backend.db.dashboard_store as dashboard_store_module
from backend.anonymize import normalize_group_code, pseudonymize
from backend.api import routes
from backend.main import app

REPO_ROOT = Path(__file__).resolve().parents[1]
API_KEY = "tutor-key"
RESEARCH_KEY = "research-key"
GOLDEN_CASE = "alpes-bank-genai-001"


# ---------------------------------------------------------------------------
# Pseudonymisierung + Gruppencode-Normalisierung
# ---------------------------------------------------------------------------

def test_pseudonymize_stable_and_irreversible(monkeypatch):
    monkeypatch.setenv("PSEUDONYM_SECRET", "s3cret")
    a = pseudonymize("21-654-321")
    b = pseudonymize("21-654-321")
    c = pseudonymize("21-654-322")
    assert a == b and a != c
    assert a.startswith("anon-") and "21-654-321" not in a
    # Idempotent: bereits pseudonymisierte Werte bleiben unverändert
    assert pseudonymize(a) == a


def test_pseudonymize_without_secret_keeps_raw(monkeypatch):
    monkeypatch.delenv("PSEUDONYM_SECRET", raising=False)
    assert pseudonymize("kennung-x") == "kennung-x"


def test_normalize_group_code():
    assert normalize_group_code(" 12 ") == "G12"
    assert normalize_group_code("g12") == "G12"
    assert normalize_group_code("Team A") == "TEAMA"
    assert normalize_group_code(None) == ""


# ---------------------------------------------------------------------------
# Submission/Session tragen Gruppe + Pseudonym
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(monkeypatch):
    for var in ("MONGODB_URI", "MONGODB_MAS_NAME", "MONGODB_MAS_KEY", "MONGODB_HOST"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("STUDENT_ACCESS_CODE", raising=False)
    monkeypatch.setenv("PSEUDONYM_SECRET", "s3cret")
    monkeypatch.setenv("TOADAPT_API_KEY", API_KEY)
    monkeypatch.setenv("RESEARCH_API_KEY", RESEARCH_KEY)
    routes._submissions.clear()
    routes._sessions.clear()
    return TestClient(app)


def test_submission_stores_pseudonym_and_group(client):
    res = client.post("/submissions", json={
        "user_id": "p_21-654-321", "matrikelnummer": "21-654-321",
        "group_code": "12", "case_id": GOLDEN_CASE, "target_tp": 1,
    })
    assert res.status_code == 201
    sub = routes._submissions[res.json()["submission_id"]]
    assert sub.group_code == "G12"
    assert sub.matrikelnummer.startswith("anon-")
    assert "21-654-321" not in sub.matrikelnummer
    assert sub.user_id.startswith("anon-")


def test_session_stores_pseudonym_and_group(client):
    res = client.post("/sessions", json={
        "user_id": "p_21-654-321", "group_code": "g7", "case_id": GOLDEN_CASE,
    })
    assert res.status_code == 201
    session = routes._sessions[res.json()["session_id"]]
    assert session.group_code == "G7"
    assert session.user_id.startswith("anon-")


def test_tp_endpoint_returns_schedule(client):
    res = client.get("/tp")
    assert res.status_code == 200
    data = res.json()
    assert data["current_tp"] in (1, 2, 3, 4)
    assert set(data["schedule"].keys()) == {"1", "2", "3", "4"}


# ---------------------------------------------------------------------------
# Dashboard: Tutor sieht Gruppen, Forschung sieht Einzelne
# ---------------------------------------------------------------------------

def _seed_results(monkeypatch, tmp_path):
    monkeypatch.setattr(dashboard_store_module, "RESULTS_DIR", tmp_path)

    def result(matrikel, group, pct, penalties=None):
        return {
            "submission_id": f"sub-{matrikel}-{pct}", "matrikelnummer": matrikel,
            "group_code": group, "case_id": "c", "target_tp": 1, "percentage": pct,
            "evaluated_at": "2026-07-01T10:00:00",
            "scores": [{
                "question_id": "q1", "bloom_level": 4, "max_points": 10,
                "awarded_points": pct / 10, "feedback": "x",
                "learning_objective_tags": ["wirkungskette"],
                "main_penalties": penalties or [], "missing_canvas_blocks": [],
                "needs_human_review": False, "evaluation_status": "ok",
            }],
        }

    seeds = [
        result("anon-a1", "G12", 30, ["Keine Begründung"]),
        result("anon-a2", "G12", 85),
        result("anon-b1", "G7", 90),
        result("anon-c1", "", 50),
    ]
    for i, r in enumerate(seeds):
        (tmp_path / f"r{i}.json").write_text(json.dumps(r), encoding="utf-8")


def test_groups_endpoint_returns_aggregates_without_identifiers(client, monkeypatch, tmp_path):
    _seed_results(monkeypatch, tmp_path)

    res = client.get("/dashboard/groups", headers={"X-API-Key": API_KEY})
    assert res.status_code == 200
    body = json.dumps(res.json())
    assert "anon-a1" not in body and "matrikelnummer" not in body

    groups = {g["group_code"]: g for g in res.json()}
    assert groups["G12"]["members_active"] == 2
    assert groups["G12"]["attention_high"] == 1
    assert "OHNE-GRUPPE" in groups

    detail = client.get("/dashboard/groups/G12", headers={"X-API-Key": API_KEY}).json()
    assert "anon-a1" not in json.dumps(detail)
    weak = {o["tag"]: o for o in detail["weak_objectives"]}
    assert weak["wirkungskette"]["members_below"] == 1
    assert weak["wirkungskette"]["members_total"] == 2
    assert detail["common_penalties"][0]["text"] == "Keine Begründung"

    assert client.get("/dashboard/groups/GIBTSNICHT", headers={"X-API-Key": API_KEY}).status_code == 404


def test_individual_endpoints_require_research_key(client, monkeypatch, tmp_path):
    _seed_results(monkeypatch, tmp_path)
    tutor = {"X-API-Key": API_KEY}
    research = {"X-API-Key": API_KEY, "X-Research-Key": RESEARCH_KEY}

    # Tutor-Key allein reicht NICHT für Einzelpersonen-Daten
    for path in ("/dashboard/students", "/dashboard/difficulties", "/dashboard/student/anon-a1"):
        assert client.get(path, headers=tutor).status_code == 401, path

    # Forschungs-Key (zusätzlich) öffnet sie
    assert client.get("/dashboard/students", headers=research).status_code == 200
    assert client.get("/dashboard/difficulties", headers=research).status_code == 200

    # Gruppen + Overview bleiben für Tutor:innen erreichbar
    assert client.get("/dashboard/groups", headers=tutor).status_code == 200
    assert client.get("/dashboard/overview", headers=tutor).status_code == 200


def test_research_key_fail_closed(client, monkeypatch, tmp_path):
    _seed_results(monkeypatch, tmp_path)
    monkeypatch.delenv("RESEARCH_API_KEY", raising=False)
    res = client.get("/dashboard/students", headers={"X-API-Key": API_KEY, "X-Research-Key": "x"})
    assert res.status_code == 503


# ---------------------------------------------------------------------------
# Tutor-Code-Generator
# ---------------------------------------------------------------------------

def test_generate_tutor_codes_unique_and_complete():
    spec = importlib.util.spec_from_file_location(
        "generate_tutor_codes", REPO_ROOT / "scripts" / "generate_tutor_codes.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    codes = module.generate([f"tutor{i:02d}" for i in range(1, 41)])
    assert len(codes) == 40
    assert len(set(codes.values())) == 40
    for code in codes.values():
        assert len(code) == 14 and code.count("-") == 2
        assert not any(ch in code for ch in "0O1lI")
