"""Tests für Phase-1-Härtung: Studenten-Zugangscode, Rate-Limiter, Stores."""

import asyncio

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.main import app
from backend.ratelimit import rate_limit


# ---------------------------------------------------------------------------
# Studenten-Zugangscode
# ---------------------------------------------------------------------------

def test_student_flow_open_without_configured_code(monkeypatch):
    monkeypatch.delenv("STUDENT_ACCESS_CODE", raising=False)
    client = TestClient(app)
    res = client.post("/auth/student/verify")
    assert res.status_code == 200
    assert res.json() == {"ok": True, "required": False}


def test_student_flow_requires_code_when_configured(monkeypatch):
    monkeypatch.setenv("STUDENT_ACCESS_CODE", "kohorte-hs26")
    client = TestClient(app)

    assert client.post("/auth/student/verify").status_code == 401
    assert client.post(
        "/auth/student/verify", headers={"X-Student-Access-Code": "falsch"}
    ).status_code == 401

    res = client.post(
        "/auth/student/verify", headers={"X-Student-Access-Code": "kohorte-hs26"}
    )
    assert res.status_code == 200
    assert res.json() == {"ok": True, "required": True}


def test_sessions_endpoint_guarded_by_student_code(monkeypatch):
    monkeypatch.setenv("STUDENT_ACCESS_CODE", "kohorte-hs26")
    client = TestClient(app)
    res = client.post("/sessions", json={"user_id": "u1", "case_id": "gibt-es-nicht"})
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Rate-Limiter
# ---------------------------------------------------------------------------

def _limited_app() -> FastAPI:
    test_app = FastAPI()

    @test_app.get("/limited", dependencies=[Depends(rate_limit(3, 60, scope="test"))])
    async def limited() -> dict:
        return {"ok": True}

    @test_app.get(
        "/per-item/{item_id}",
        dependencies=[Depends(rate_limit(2, 60, scope="item", by_path_param="item_id"))],
    )
    async def per_item(item_id: str) -> dict:
        return {"item": item_id}

    return test_app


def test_rate_limit_blocks_after_threshold():
    client = TestClient(_limited_app())
    for _ in range(3):
        assert client.get("/limited").status_code == 200
    res = client.get("/limited")
    assert res.status_code == 429
    assert "Retry-After" in res.headers


def test_rate_limit_keys_by_path_param():
    client = TestClient(_limited_app())
    for _ in range(2):
        assert client.get("/per-item/a").status_code == 200
    assert client.get("/per-item/a").status_code == 429
    # Anderer Schlüssel → eigenes Kontingent.
    assert client.get("/per-item/b").status_code == 200


# ---------------------------------------------------------------------------
# Stores ohne Mongo (Datei-/No-op-Fallback)
# ---------------------------------------------------------------------------

def test_session_store_noop_without_mongo(monkeypatch):
    for var in ("MONGODB_URI", "MONGODB_MAS_NAME", "MONGODB_MAS_KEY", "MONGODB_HOST"):
        monkeypatch.delenv(var, raising=False)

    from backend.db.session_store import session_store
    from backend.models.session import Session

    session = Session(session_id="s1", user_id="u1", case_id="c1", tp_phase=1)
    session_store.save(session)  # darf ohne Mongo nicht werfen
    assert session_store.load("s1") is None


def test_dashboard_store_file_fallback(tmp_path, monkeypatch):
    for var in ("MONGODB_URI", "MONGODB_MAS_NAME", "MONGODB_MAS_KEY", "MONGODB_HOST"):
        monkeypatch.delenv(var, raising=False)

    import backend.db.dashboard_store as dashboard_store_module

    monkeypatch.setattr(dashboard_store_module, "RESULTS_DIR", tmp_path)
    store = dashboard_store_module.DashboardStore()

    store.save_result({"submission_id": "sub-1", "percentage": 80.0})
    results = store.load_all()
    assert len(results) == 1
    assert results[0]["submission_id"] == "sub-1"


# ---------------------------------------------------------------------------
# LLM-Client: geteilte Instanz + Concurrency-Limit vorhanden
# ---------------------------------------------------------------------------

def test_openrouter_client_is_shared():
    from backend.llm import OpenRouterClient

    a = OpenRouterClient(api_key="test-key")
    b = OpenRouterClient(api_key="test-key")
    assert a.client is b.client


async def test_llm_semaphore_limits_concurrency(monkeypatch):
    import backend.llm as llm

    monkeypatch.setattr(llm, "LLM_MAX_CONCURRENCY", 2)
    llm._semaphores.clear()

    active = 0
    peak = 0

    async def fake_call() -> None:
        nonlocal active, peak
        async with llm._semaphore():
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1

    await asyncio.gather(*(fake_call() for _ in range(6)))
    assert peak <= 2
