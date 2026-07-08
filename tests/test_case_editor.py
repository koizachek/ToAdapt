"""Tests für den interaktiven Case-Editor (Phase 2): Validierung, Edit, Approve-Gate."""

import pytest
from fastapi.testclient import TestClient

import backend.cases.manager as manager_module
from backend.cases.validator import validate_case
from backend.main import app
from backend.models.case import Case, CaseExhibit, CaseQuestion, CaseSection, CaseStatus

API_KEY = "test-admin-key"


def _sample_case(**overrides) -> Case:
    defaults = dict(
        case_id="test-case-001",
        title="Nordwind Logistik — Wachstum unter Druck",
        industry="Logistics",
        country="Deutschland",
        tagline="Ein Mittelständler muss sich zwischen Expansion und Konsolidierung entscheiden.",
        difficulty="tp1",
        target_tp=1,
        language="de",
        sections=[
            CaseSection(section_id=f"s{i}", title=f"Abschnitt {i}", content=f"Inhalt {i}.")
            for i in range(1, 5)
        ],
        exhibits=[
            CaseExhibit(exhibit_id=f"e{i}", title=f"Exhibit {i}", content="| a | b |", exhibit_type="table")
            for i in range(1, 4)
        ],
        questions=[
            CaseQuestion(
                question_id=f"q{i}", phase=1, bloom_level=bloom, text=f"Frage {i}?",
                max_points=points, rubric_reference="tp1_rubric.json",
            )
            for i, (bloom, points) in enumerate([(2, 8), (3, 8), (4, 9)], start=1)
        ],
    )
    defaults.update(overrides)
    return Case(**defaults)


@pytest.fixture()
def env(monkeypatch, tmp_path):
    """Isolierter Pool (tmp), kein Mongo, Admin-API-Key gesetzt."""
    for var in ("MONGODB_URI", "MONGODB_MAS_NAME", "MONGODB_MAS_KEY", "MONGODB_HOST"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.delenv("STUDENT_ACCESS_CODE", raising=False)
    monkeypatch.setenv("TOADAPT_API_KEY", API_KEY)
    monkeypatch.setattr(manager_module, "POOL_DIR", tmp_path)
    return TestClient(app)


def _auth() -> dict:
    return {"X-API-Key": API_KEY}


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def test_validator_accepts_clean_case():
    report = validate_case(_sample_case())
    assert report.ok
    assert not any(i.level == "error" for i in report.issues)


def test_validator_flags_forbidden_framework_name():
    case = _sample_case()
    case.sections[0].content = "Nutzt hier Porter zur Analyse der Branche."
    report = validate_case(case)
    assert not report.ok
    assert any(i.code == "forbidden_framework_name" and i.location == "section:s1" for i in report.issues)


def test_validator_flags_reserved_case_reference():
    case = _sample_case()
    case.questions[0].text = "Vergleichen Sie mit NORDIC HOME."
    report = validate_case(case)
    assert not report.ok
    assert any(i.code == "reserved_case_reference" for i in report.issues)


def test_validator_warns_on_missing_bloom_coverage():
    case = _sample_case()
    case.questions = case.questions[:1]  # nur Bloom 2
    report = validate_case(case)
    assert report.ok  # Warnungen blockieren nicht
    assert any(i.code == "bloom_coverage" for i in report.issues)


# ---------------------------------------------------------------------------
# Editor-Endpoints
# ---------------------------------------------------------------------------

def test_patch_updates_fields_and_bumps_revision(env):
    case = _sample_case()
    manager_module.case_manager.save(case)

    res = env.patch(
        f"/admin/cases/{case.case_id}",
        json={"editor": "Prof. Meier", "tagline": "Neue Tagline."},
        headers=_auth(),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["tagline"] == "Neue Tagline."
    assert data["revision"] == 2
    assert data["edit_history"][-1]["action"] == "edited"


def test_patch_requires_api_key(env):
    case = _sample_case()
    manager_module.case_manager.save(case)
    res = env.patch(f"/admin/cases/{case.case_id}", json={"title": "X"})
    assert res.status_code == 401


def test_editing_approved_case_resets_to_draft(env):
    case = _sample_case(status=CaseStatus.APPROVED)
    manager_module.case_manager.save(case)

    res = env.patch(
        f"/admin/cases/{case.case_id}",
        json={"editor": "Prof. Meier", "title": "Geänderter Titel"},
        headers=_auth(),
    )
    assert res.status_code == 200
    assert res.json()["status"] == CaseStatus.DRAFT


def test_approve_blocked_by_validation_error_unless_forced(env):
    case = _sample_case()
    case.sections[0].content = "Wendet die Transaktionskosten-Logik nach Porter an."
    manager_module.case_manager.save(case)

    res = env.post(
        f"/admin/cases/{case.case_id}/approve",
        json={"reviewer": "Prof. Meier"},
        headers=_auth(),
    )
    assert res.status_code == 422
    assert any(i["code"] == "forbidden_framework_name" for i in res.json()["detail"]["issues"])

    res = env.post(
        f"/admin/cases/{case.case_id}/approve",
        json={"reviewer": "Prof. Meier", "force": True},
        headers=_auth(),
    )
    assert res.status_code == 200
    assert res.json()["status"] == CaseStatus.APPROVED
    assert "erzwungen" in res.json()["review_notes"]


def test_validate_endpoint_returns_report(env):
    case = _sample_case()
    manager_module.case_manager.save(case)
    res = env.get(f"/admin/cases/{case.case_id}/validate", headers=_auth())
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_retire_removes_case_from_pool(env):
    case = _sample_case(status=CaseStatus.APPROVED)
    manager_module.case_manager.save(case)

    res = env.post(
        f"/admin/cases/{case.case_id}/retire",
        json={"reviewer": "Prof. Meier", "notes": "Semesterende"},
        headers=_auth(),
    )
    assert res.status_code == 200
    assert res.json()["status"] == CaseStatus.RETIRED
    assert manager_module.case_manager.approved_pool() == []


def test_regenerate_section_replaces_content(env, monkeypatch):
    case = _sample_case()
    manager_module.case_manager.save(case)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    async def fake_complete(self, *, system, messages, max_tokens):
        return '{"section_id": "s1", "title": "Neuer Titel", "content": "Neuer Inhalt."}'

    monkeypatch.setattr("backend.llm.OpenRouterClient.complete", fake_complete)

    res = env.post(
        f"/admin/cases/{case.case_id}/regenerate",
        json={
            "editor": "Prof. Meier",
            "target": "section",
            "target_id": "s1",
            "instructions": "Mehr Spannung im Einstieg.",
        },
        headers=_auth(),
    )
    assert res.status_code == 200
    data = res.json()
    section = next(s for s in data["sections"] if s["section_id"] == "s1")
    assert section["content"] == "Neuer Inhalt."
    assert data["revision"] == 2
    assert data["edit_history"][-1]["action"] == "regenerated"


def test_regenerate_unknown_target_returns_400(env, monkeypatch):
    case = _sample_case()
    manager_module.case_manager.save(case)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    res = env.post(
        f"/admin/cases/{case.case_id}/regenerate",
        json={"editor": "x", "target": "section", "target_id": "gibt-es-nicht"},
        headers=_auth(),
    )
    assert res.status_code == 400


def test_generator_strip_json_fences():
    from backend.cases.generator import _strip_json_fences

    assert _strip_json_fences('{"a": 1}') == '{"a": 1}'
    assert _strip_json_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
