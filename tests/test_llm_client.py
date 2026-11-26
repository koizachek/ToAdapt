"""Tests für Prompt-Caching und Request-Parameter im Requesty-Client.

Kein echter LLM-Call: der AsyncOpenAI-Client wird durch einen Stub ersetzt,
der die Request-Parameter aufzeichnet — geprüft wird, WAS gesendet würde.
"""

import asyncio
from types import SimpleNamespace

import pytest

from backend.llm import (
    RequestyClient,
    build_request_messages,
    prompt_caching_enabled,
)


# ---------------------------------------------------------------------------
# Pure Helfer
# ---------------------------------------------------------------------------

def test_prompt_caching_enabled_default_and_off_switch(monkeypatch):
    monkeypatch.delenv("LLM_PROMPT_CACHING", raising=False)
    assert prompt_caching_enabled() is True
    for off in ("0", "false", "OFF", " no "):
        monkeypatch.setenv("LLM_PROMPT_CACHING", off)
        assert prompt_caching_enabled() is False


def test_build_request_messages_plain_system(monkeypatch):
    monkeypatch.delenv("LLM_PROMPT_CACHING", raising=False)
    result = build_request_messages("SYS", [{"role": "user", "content": "hi"}])
    assert result[0] == {"role": "system", "content": "SYS"}
    assert result[1]["content"] == "hi"


def test_build_request_messages_with_cache_breakpoint(monkeypatch):
    monkeypatch.delenv("LLM_PROMPT_CACHING", raising=False)
    result = build_request_messages(
        "SYS", [{"role": "user", "content": "hi"}], cache_system=True
    )
    system = result[0]
    assert system["role"] == "system"
    # Inhalt bleibt identisch, nur als Content-Block mit cache_control verpackt
    assert system["content"] == [
        {"type": "text", "text": "SYS", "cache_control": {"type": "ephemeral"}}
    ]


def test_cache_flag_respects_off_switch(monkeypatch):
    monkeypatch.setenv("LLM_PROMPT_CACHING", "0")
    result = build_request_messages("SYS", [], cache_system=True)
    assert result[0] == {"role": "system", "content": "SYS"}


def test_no_system_message_when_empty():
    assert build_request_messages(None, [{"role": "user", "content": "x"}], cache_system=True) == [
        {"role": "user", "content": "x"}
    ]


# ---------------------------------------------------------------------------
# complete(): Request-Parameter, die tatsächlich gesendet würden
# ---------------------------------------------------------------------------

class _StubCompletions:
    def __init__(self):
        self.last_kwargs = None

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(
            model="mistral/mistral-medium-3-5",
            usage=SimpleNamespace(
                prompt_tokens=3000, completion_tokens=200, total_tokens=3200,
                prompt_tokens_details=SimpleNamespace(cached_tokens=2700),
            ),
            choices=[SimpleNamespace(message=SimpleNamespace(content="Antwort"))],
        )


def _stubbed_client(monkeypatch) -> tuple[RequestyClient, _StubCompletions]:
    monkeypatch.setenv("REQUESTY_API_KEY", "test-key")
    client = RequestyClient(api_key="test-key")
    stub = _StubCompletions()
    client.client = SimpleNamespace(chat=SimpleNamespace(completions=stub))
    return client, stub


def test_complete_sends_plain_openai_request(monkeypatch):
    """Kein Router-Sonderfeld im Body: der Fallback liegt in der
    Requesty-Policy (REQUESTY_MODEL=policy/<name>), nicht im Request."""
    client, stub = _stubbed_client(monkeypatch)

    text = asyncio.run(client.complete(
        system="SYS", messages=[{"role": "user", "content": "hi"}],
        max_tokens=100, cache_system=True,
    ))
    assert text == "Antwort"
    assert set(stub.last_kwargs) == {"model", "messages", "max_tokens"}
    assert stub.last_kwargs["model"] == client.model
    assert stub.last_kwargs["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral"}


def test_complete_without_cache_keeps_plain_system_string(monkeypatch):
    client, stub = _stubbed_client(monkeypatch)

    asyncio.run(client.complete(
        system="SYS", messages=[{"role": "user", "content": "hi"}], max_tokens=100,
    ))
    assert stub.last_kwargs["messages"][0]["content"] == "SYS"


def test_policy_model_is_passed_through(monkeypatch):
    monkeypatch.setenv("REQUESTY_API_KEY", "test-key")
    client = RequestyClient(api_key="test-key", model="policy/toadapt")
    assert client.model == "policy/toadapt"


def test_complete_raises_on_empty_response(monkeypatch):
    client, stub = _stubbed_client(monkeypatch)

    async def empty_create(**kwargs):
        return SimpleNamespace(
            model=client.model, usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content=""))],
        )

    stub.create = empty_create
    with pytest.raises(RuntimeError):
        asyncio.run(client.complete(system=None, messages=[{"role": "user", "content": "x"}], max_tokens=10))
