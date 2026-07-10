"""Tests für die Lasttest-Werkzeuge (scripts/llm_stub.py + scripts/load_test.py).

Der Stub muss Antworten liefern, die die ECHTEN Verarbeitungspfade bestehen:
Chat-Antworten den guardrail_check, Judge-Antworten die JSON-Pipeline des
Evaluators — sonst misst der Lasttest einen unrealistischen Fehlerpfad.
"""

from fastapi.testclient import TestClient

import scripts.llm_stub as llm_stub
from backend.agents.orchestrator import guardrail_check
from backend.evaluator.rubric_evaluator import parse_evaluation_payload
from scripts.load_test import percentile, render_report, spoofed_ip, summarize


# ---------------------------------------------------------------------------
# LLM-Stub
# ---------------------------------------------------------------------------

def _stub_client(monkeypatch) -> TestClient:
    monkeypatch.setattr(llm_stub, "LATENCY_MS", 0)
    monkeypatch.setattr(llm_stub, "JITTER_MS", 0)
    return TestClient(llm_stub.app)


def test_stub_chat_reply_passes_guardrails(monkeypatch):
    client = _stub_client(monkeypatch)
    res = client.post("/v1/chat/completions", json={
        "model": "stub",
        "messages": [{"role": "user", "content": "Wie soll das Unternehmen wachsen?"}],
    })
    assert res.status_code == 200
    text = res.json()["choices"][0]["message"]["content"]
    for tp in (1, 2, 3, 4):
        ok, reason = guardrail_check(text, tp)
        assert ok, f"Stub-Antwort verletzt Guardrail (TP{tp}): {reason}"
    assert res.json()["usage"]["prompt_tokens"] > 0


def test_stub_judge_reply_parses_as_evaluation(monkeypatch):
    client = _stub_client(monkeypatch)
    res = client.post("/chat/completions", json={
        "model": "stub",
        "messages": [{"role": "user", "content": "… Antworte mit einem JSON-Objekt: …"}],
    })
    payload = parse_evaluation_payload(res.json()["choices"][0]["message"]["content"])
    assert isinstance(payload["awarded_points"], (int, float))
    assert payload["judge_confidence"] == "high"
    assert payload["needs_human_review"] is False


# ---------------------------------------------------------------------------
# Lasttest-Helfer (pur)
# ---------------------------------------------------------------------------

def test_percentile_nearest_rank():
    assert percentile([], 95) == 0.0
    assert percentile([1.0], 95) == 1.0
    values = [float(i) for i in range(1, 102)]   # 1..101, Median exakt
    assert percentile(values, 50) == 51.0
    assert percentile(values, 95) == 96.0
    assert percentile([3.0, 1.0, 2.0], 100) == 3.0


def test_summarize_buckets_statuses():
    samples = [
        ("chat", 200, 1.0), ("chat", 200, 3.0), ("chat", 429, 0.1),
        ("chat", 500, 0.2), ("chat", 0, 0.3), ("submit", 404, 0.1),
    ]
    by_op = summarize(samples)
    chat = by_op["chat"]
    assert (chat["n"], chat["ok"], chat["s429"], chat["s5xx"]) == (5, 2, 1, 2)
    assert chat["max"] == 3.0            # nur erfolgreiche Latenzen zählen
    assert by_op["submit"]["s4xx"] == 1


def test_spoofed_ips_unique_for_typical_cohort():
    ips = {spoofed_ip(i) for i in range(300)}
    assert len(ips) == 300


def test_render_report_evaluates_gates():
    class Args:
        base_url = "http://x"
        students = 2
        tutors = 1
        turns = 5
        ramp_seconds = 10.0

    by_op = {
        "chat": {"n": 10, "ok": 10, "s429": 0, "s4xx": 0, "s5xx": 0,
                 "p50": 1.0, "p95": 2.0, "p99": 3.0, "max": 3.0},
        "submit": {"n": 2, "ok": 2, "s429": 0, "s4xx": 0, "s5xx": 0,
                   "p50": 5.0, "p95": 8.0, "p99": 9.0, "max": 9.0},
    }
    report = render_report(Args(), by_op, wall_seconds=42.0)
    assert "PASS: Chat p95 < 10 s" in report
    assert "PASS: Submit p95 < 30 s" in report
    assert "PASS: Keine 5xx" in report

    by_op["chat"]["s5xx"] = 3
    report = render_report(Args(), by_op, wall_seconds=42.0)
    assert "FAIL: Keine 5xx" in report
