"""Tests für Prompt-Caching und Fallback-Routing im OpenRouter-Client.

Kein echter LLM-Call: der AsyncOpenAI-Client wird durch einen Stub ersetzt,
der die Request-Parameter aufzeichnet — geprüft wird, WAS gesendet würde.
"""

import asyncio
from types import SimpleNamespace

import pytest

from backend.llm import (
    OpenRouterClient,
    build_request_messages,
    fallback_models,
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


def test_fallback_models_parsing(monkeypatch):
    monkeypatch.delenv("OPENROUTER_FALLBACK_MODELS", raising=False)
    assert fallback_models() == []
    monkeypatch.setenv("OPENROUTER_FALLBACK_MODELS", "openai/gpt-4.1, google/gemini-2.5-pro ,")
    assert fallback_models() == ["openai/gpt-4.1", "google/gemini-2.5-pro"]


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
            model="openai/gpt-4.1",  # simuliert: Fallback hat übernommen
            usage=SimpleNamespace(
                prompt_tokens=3000, completion_tokens=200, total_tokens=3200,
                prompt_tokens_details=SimpleNamespace(cached_tokens=2700),
            ),
            choices=[SimpleNamespace(message=SimpleNamespace(content="Antwort"))],
        )


def _stubbed_client(monkeypatch) -> tuple[OpenRouterClient, _StubCompletions]:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    client = OpenRouterClient(api_key="test-key")
    stub = _StubCompletions()
    client.client = SimpleNamespace(chat=SimpleNamespace(completions=stub))
    return client, stub


def test_complete_sends_fallback_routing_list(monkeypatch):
    monkeypatch.setenv("OPENROUTER_FALLBACK_MODELS", "openai/gpt-4.1")
    client, stub = _stubbed_client(monkeypatch)

    text = asyncio.run(client.complete(
        system="SYS", messages=[{"role": "user", "content": "hi"}],
        max_tokens=100, cache_system=True,
    ))
    assert text == "Antwort"
    assert stub.last_kwargs["extra_body"] == {"models": [client.model, "openai/gpt-4.1"]}
    assert stub.last_kwargs["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral"}


def test_complete_without_fallbacks_sends_no_models_list(monkeypatch):
    monkeypatch.delenv("OPENROUTER_FALLBACK_MODELS", raising=False)
    client, stub = _stubbed_client(monkeypatch)

    asyncio.run(client.complete(
        system="SYS", messages=[{"role": "user", "content": "hi"}], max_tokens=100,
    ))
    assert stub.last_kwargs["extra_body"] is None
    # ohne cache_system bleibt der System-Prompt ein einfacher String
    assert stub.last_kwargs["messages"][0]["content"] == "SYS"


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
