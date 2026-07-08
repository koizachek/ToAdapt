"""Gemeinsamer LLM-Client für OpenRouter.

Härtung für den Betrieb mit vielen gleichzeitigen Nutzern:
- Ein geteilter AsyncOpenAI-Client pro API-Key (Connection-Reuse statt
  Client-pro-Request).
- Timeout und automatische Retries mit exponentiellem Backoff (429/5xx/
  Verbindungsfehler) über die OpenAI-SDK-Mechanik.
- Globales Concurrency-Limit, damit Lastspitzen nicht ungebremst auf
  OpenRouter durchschlagen.
- Token-Verbrauch wird pro Call geloggt (Kostenmonitoring).
"""

import asyncio
import os

import structlog
from openai import AsyncOpenAI

logger = structlog.get_logger(__name__)

OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
DEFAULT_OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")

LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "60"))
LLM_MAX_RETRIES = int(os.environ.get("LLM_MAX_RETRIES", "2"))
LLM_MAX_CONCURRENCY = int(os.environ.get("LLM_MAX_CONCURRENCY", "16"))

_shared_clients: dict[str, AsyncOpenAI] = {}
# Semaphoren pro Event-Loop, da asyncio-Primitive an den Loop gebunden sind
# (Tests erzeugen pro Testfall einen neuen Loop).
_semaphores: dict[int, asyncio.Semaphore] = {}


def get_openrouter_key() -> str:
    return os.environ.get("OPENROUTER_API_KEY", "")


def get_openrouter_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    referer = os.environ.get("OPENROUTER_HTTP_REFERER", "http://localhost:3000")
    title = os.environ.get("OPENROUTER_APP_TITLE", "ToAdapt")

    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-Title"] = title

    return headers


def _shared_client(api_key: str) -> AsyncOpenAI:
    client = _shared_clients.get(api_key)
    if client is None:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
            default_headers=get_openrouter_headers(),
            timeout=LLM_TIMEOUT_SECONDS,
            max_retries=LLM_MAX_RETRIES,
        )
        _shared_clients[api_key] = client
    return client


def _semaphore() -> asyncio.Semaphore:
    loop_id = id(asyncio.get_running_loop())
    sem = _semaphores.get(loop_id)
    if sem is None:
        sem = asyncio.Semaphore(LLM_MAX_CONCURRENCY)
        _semaphores[loop_id] = sem
    return sem


class OpenRouterClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = api_key or get_openrouter_key()
        if not key:
            raise ValueError("OPENROUTER_API_KEY nicht konfiguriert")

        self.model = model or DEFAULT_OPENROUTER_MODEL
        self.client = _shared_client(key)

    async def complete(
        self,
        *,
        system: str | None,
        messages: list[dict[str, str]],
        max_tokens: int,
    ) -> str:
        request_messages: list[dict[str, str]] = []
        if system:
            request_messages.append({"role": "system", "content": system})
        request_messages.extend(messages)

        async with _semaphore():
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=request_messages,
                max_tokens=max_tokens,
            )

        usage = getattr(response, "usage", None)
        if usage is not None:
            logger.info(
                "llm_call_completed",
                model=self.model,
                prompt_tokens=getattr(usage, "prompt_tokens", None),
                completion_tokens=getattr(usage, "completion_tokens", None),
                total_tokens=getattr(usage, "total_tokens", None),
            )

        text = response.choices[0].message.content
        if not text:
            raise RuntimeError("OpenRouter lieferte keine Textantwort")
        return text
