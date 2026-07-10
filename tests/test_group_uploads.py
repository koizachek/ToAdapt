"""Tests für den Master-Tutor-Upload der Gruppenarbeiten (ZIP → Judge).

Abgedeckt: ZIP-/PDF-Verarbeitung (pur, ohne LLM), Deckblatt-Parsing,
fail-closed Auth, Upload-Flow mit gemocktem LLM, technical_fallback-Kette,
manuelle Gruppenzuordnung und die Dashboard-Integration (Gruppenarbeiten
als zweite Datenquelle in den Gruppen-Aggregaten).
"""

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

import backend.db.dashboard_store as dashboard_store_module
import backend.db.group_upload_store as group_upload_store_module
from backend.group_uploads.extraction import (
    ZipValidationError,
    extract_pdf_text,
    list_pdf_entries,
    parse_group_code,
)
from backend.llm import OpenRouterClient
from backend.main import app

API_KEY = "tutor-key"


# ---------------------------------------------------------------------------
# Fixtures & Helfer
# ---------------------------------------------------------------------------

def _minimal_pdf(text: str) -> bytes:
    """Erzeugt ein minimales, valides Ein-Seiten-PDF mit extrahierbarem Text
    (synthetisch — keine echten Teilnehmerdaten)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n"
    ).encode()
    return bytes(out)


def _zip_of(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


VALID_JUDGE_PAYLOAD = json.dumps({
    "awarded_points": 18,
    "feedback": "Solide Argumentationslinie mit klarem Fallbezug.",
    "learning_objective_tags": ["evaluieren"],
    "canvas_alignment_score": 0.8,
    "addressed_canvas_blocks": ["value_propositions"],
    "missing_canvas_blocks": [],
    "canvas_rationale": "ok",
    "judge_confidence": "high",
    "score_band": "solid",
    "main_strengths": ["klare Entscheidung"],
    "main_penalties": [],
    "needs_human_review": False,
})


@pytest.fixture()
def client(monkeypatch, tmp_path):
    for var in ("MONGODB_URI", "MONGODB_MAS_NAME", "MONGODB_MAS_KEY", "MONGODB_HOST"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("TOADAPT_API_KEY", API_KEY)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    uploads_dir = tmp_path / "group_uploads"
    uploads_dir.mkdir()
    monkeypatch.setattr(group_upload_store_module, "RESULTS_DIR", uploads_dir)
    dashboard_dir = tmp_path / "dashboard"
    dashboard_dir.mkdir()
    monkeypatch.setattr(dashboard_store_module, "RESULTS_DIR", dashboard_dir)
    return TestClient(app)


def _mock_judge(monkeypatch, response_text: str):
    async def fake_complete(self, *, system, messages, max_tokens):
        return response_text

    monkeypatch.setattr(OpenRouterClient, "complete", fake_complete)


# ---------------------------------------------------------------------------
# Extraktion (pur, ohne LLM)
# ---------------------------------------------------------------------------

def test_parse_group_code_variants():
    assert parse_group_code("BWL A Abgabe\nGruppe 12\nHS 2026") == "G12"
    assert parse_group_code("Gruppennummer: 7") == "G7"
    assert parse_group_code("Gruppen-Nr. G03") == "G03"
    assert parse_group_code("Group 5 — Running Case") == "G5"
    assert parse_group_code("Group number: 12") == "G12"
    assert parse_group_code("Deckblatt ohne Indikator") == ""


def test_parse_group_code_only_reads_cover_area():
    # Erwähnungen anderer Gruppen tief im Dokument dürfen nicht matchen.
    text = "Deckblatt ohne Indikator" + " Fülltext." * 400 + " Gruppe 99"
    assert parse_group_code(text) == ""


def test_extract_text_and_group_from_minimal_pdf():
    pdf = _minimal_pdf("Gruppe 12 - Management Memo")
    text = extract_pdf_text(pdf)
    assert "Gruppe 12" in text
    assert parse_group_code(text) == "G12"


def test_extract_rejects_unreadable_pdf():
    with pytest.raises(ValueError):
        extract_pdf_text(b"kein pdf")


def test_list_pdf_entries_filters_and_validates():
    payload = _zip_of({
        "abgaben/memo_g12.pdf": _minimal_pdf("Gruppe 12"),
        "__MACOSX/._memo_g12.pdf": b"junk",
        "notizen.txt": b"ignorieren",
    })
    entries = list_pdf_entries(payload)
    assert [name for name, _ in entries] == ["memo_g12.pdf"]

    with pytest.raises(ZipValidationError):
        list_pdf_entries(b"kein zip")
    with pytest.raises(ZipValidationError):
        list_pdf_entries(_zip_of({"nur_text.txt": b"x"}))  # keine PDFs


# ---------------------------------------------------------------------------
# Auth: fail-closed
# ---------------------------------------------------------------------------

def test_group_uploads_fail_closed_without_api_key(client, monkeypatch):
    monkeypatch.delenv("TOADAPT_API_KEY", raising=False)
    assert client.get("/group-uploads").status_code == 503


def test_group_uploads_reject_wrong_api_key(client):
    assert client.get("/group-uploads", headers={"X-API-Key": "falsch"}).status_code == 401


# ---------------------------------------------------------------------------
# Upload-Flow (LLM gemockt)
# ---------------------------------------------------------------------------

def _upload(client, zip_bytes: bytes, target_tp: int = 2):
    return client.post(
        "/group-uploads",
        headers={"X-API-Key": API_KEY},
        files={"file": ("batch.zip", zip_bytes, "application/zip")},
        data={"target_tp": str(target_tp)},
    )


def test_upload_evaluates_assigns_and_stores(client, monkeypatch):
    _mock_judge(monkeypatch, VALID_JUDGE_PAYLOAD)
    payload = _zip_of({
        "memo_g12.pdf": _minimal_pdf("Gruppe 12 - Management Memo"),
        "memo_ohne.pdf": _minimal_pdf("Memo ohne Deckblatt-Indikator"),
    })

    res = _upload(client, payload, target_tp=2)
    assert res.status_code == 200
    batch = res.json()
    assert batch["evaluated_count"] == 2
    assert batch["unassigned_count"] == 1
    assert batch["failed_count"] == 0

    by_name = {u["filename"]: u for u in batch["uploads"]}
    assigned = by_name["memo_g12.pdf"]
    assert assigned["group_code"] == "G12"
    assert assigned["max_points"] == 24            # TP2-Skala (Golden Case q2)
    assert assigned["total_points"] == 18
    assert assigned["percentage"] == 75.0
    assert assigned["evaluation_status"] == "ok"
    assert by_name["memo_ohne.pdf"]["group_code"] == ""

    # Persistiert (Datei-Fallback des Stores) und über GET abrufbar
    listed = client.get("/group-uploads", headers={"X-API-Key": API_KEY}).json()
    assert {u["filename"] for u in listed} == {"memo_g12.pdf", "memo_ohne.pdf"}


def test_upload_with_garbage_llm_yields_technical_fallback(client, monkeypatch):
    _mock_judge(monkeypatch, "das ist kein json")
    res = _upload(client, _zip_of({"memo.pdf": _minimal_pdf("Gruppe 3")}), target_tp=4)
    assert res.status_code == 200
    upload = res.json()["uploads"][0]
    assert upload["evaluation_status"] == "technical_fallback"
    assert upload["needs_human_review"] is True
    assert upload["total_points"] == 0.0
    assert upload["max_points"] == 30              # TP4-Skala


def test_upload_llm_transport_error_falls_back_instead_of_500(client, monkeypatch):
    async def failing_complete(self, *, system, messages, max_tokens):
        raise RuntimeError("openrouter timeout")

    monkeypatch.setattr(OpenRouterClient, "complete", failing_complete)
    res = _upload(client, _zip_of({"memo.pdf": _minimal_pdf("Gruppe 3")}), target_tp=1)
    assert res.status_code == 200
    upload = res.json()["uploads"][0]
    assert upload["evaluation_status"] == "technical_fallback"
    assert upload["needs_human_review"] is True


def test_upload_unreadable_pdf_is_reported_not_crashed(client, monkeypatch):
    _mock_judge(monkeypatch, VALID_JUDGE_PAYLOAD)
    res = _upload(client, _zip_of({"scan.pdf": b"%PDF-1.4 kaputt"}))
    assert res.status_code == 200
    batch = res.json()
    assert batch["failed_count"] == 1
    assert batch["uploads"][0]["status"] == "extraction_failed"
    assert batch["uploads"][0]["needs_human_review"] is True


def test_upload_rejects_invalid_tp_and_bad_zip(client, monkeypatch):
    _mock_judge(monkeypatch, VALID_JUDGE_PAYLOAD)
    assert _upload(client, _zip_of({"m.pdf": _minimal_pdf("Gruppe 1")}), target_tp=9).status_code == 422
    assert _upload(client, b"kein zip").status_code == 400


def test_patch_group_code_assigns_unassigned_upload(client, monkeypatch):
    _mock_judge(monkeypatch, VALID_JUDGE_PAYLOAD)
    res = _upload(client, _zip_of({"memo.pdf": _minimal_pdf("ohne Indikator")}))
    upload_id = res.json()["uploads"][0]["upload_id"]

    patched = client.patch(
        f"/group-uploads/{upload_id}",
        headers={"X-API-Key": API_KEY},
        json={"group_code": " g7 "},
    )
    assert patched.status_code == 200
    assert patched.json()["group_code"] == "G7"

    assert client.patch(
        f"/group-uploads/{upload_id}",
        headers={"X-API-Key": API_KEY},
        json={"group_code": "  "},
    ).status_code == 422
    assert client.patch(
        "/group-uploads/gibt-es-nicht",
        headers={"X-API-Key": API_KEY},
        json={"group_code": "G1"},
    ).status_code == 404


# ---------------------------------------------------------------------------
# Dashboard-Integration: Gruppenarbeiten als zweite Datenquelle
# ---------------------------------------------------------------------------

def _seed_dashboard_result(dirpath, matrikel: str, group: str, pct: float):
    result = {
        "submission_id": f"sub-{matrikel}", "matrikelnummer": matrikel,
        "group_code": group, "case_id": "c", "target_tp": 1, "percentage": pct,
        "evaluated_at": "2026-07-01T10:00:00",
        "scores": [{
            "question_id": "q1", "bloom_level": 4, "max_points": 10,
            "awarded_points": pct / 10, "feedback": "x",
            "learning_objective_tags": ["wirkungskette"],
            "main_penalties": [], "missing_canvas_blocks": [],
            "needs_human_review": False, "evaluation_status": "ok",
        }],
    }
    (dirpath / f"{matrikel}.json").write_text(json.dumps(result), encoding="utf-8")


def test_dashboard_groups_merge_individual_and_group_work(client, monkeypatch, tmp_path):
    _seed_dashboard_result(dashboard_store_module.RESULTS_DIR, "anon-a1", "G12", 80)

    _mock_judge(monkeypatch, VALID_JUDGE_PAYLOAD)
    _upload(client, _zip_of({"memo_g12.pdf": _minimal_pdf("Gruppe 12")}), target_tp=2)
    _upload(client, _zip_of({"memo_g99.pdf": _minimal_pdf("Gruppe 99")}), target_tp=3)

    groups = client.get("/dashboard/groups", headers={"X-API-Key": API_KEY}).json()
    by_code = {g["group_code"]: g for g in groups}

    # G12: beide Datenquellen
    assert by_code["G12"]["submissions_count"] == 1
    assert by_code["G12"]["group_work_count"] == 1
    assert by_code["G12"]["group_work_avg_pct"] == 75.0

    # G99: nur Gruppenarbeit, keine Individual-Submissions — trotzdem sichtbar
    assert by_code["G99"]["members_active"] == 0
    assert by_code["G99"]["group_work_count"] == 1

    detail = client.get("/dashboard/groups/G12", headers={"X-API-Key": API_KEY}).json()
    assert len(detail["group_work"]) == 1
    assert detail["group_work"][0]["filename"] == "memo_g12.pdf"
    assert detail["group_work"][0]["target_tp"] == 2
    # Einzelkennungen verlassen die Gruppen-Endpoints weiterhin nicht
    assert "anon-a1" not in json.dumps(detail)
