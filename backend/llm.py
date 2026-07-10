"""Gemeinsamer LLM-Client für OpenRouter.

Härtung für den Betrieb mit vielen gleichzeitigen Nutzern:
- Ein geteilter AsyncOpenAI-Client pro API-Key (Connection-Reuse statt
  Client-pro-Request).
- Timeout und automatische Retries mit exponentiellem Backoff (429/5xx/
  Verbindungsfehler) über die OpenAI-SDK-Mechanik.
- Globales Concurrency-Limit, damit Lastspitzen nicht ungebremst auf
  OpenRouter durchschlagen.
- Token-Verbrauch wird pro Call geloggt (Kostenmonitoring), inkl. gecachter
  Prompt-Token.
- Prompt-Caching (Anthropic via cache_control): der System-Prompt des Chats
  (Agent-Prompt + kompletter Case, ~3k Token) wird serverseitig gecacht —
  Folge-Turns zahlen dafür nur ~10 % des Input-Preises. Für andere Provider
  ignoriert OpenRouter das Feld. Abschaltbar via LLM_PROMPT_CACHING=0.
- Fallback-Modelle (OpenRouter Model-Routing): OPENROUTER_FALLBACK_MODELS
  (kommagetrennt) wird als `models`-Liste mitgeschickt — fällt der primäre
  Provider aus (Ausfall, Rate-Limit), routet OpenRouter denselben Request
  automatisch ans nächste Modell, damit Lernende weiterarbeiten können.
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


def prompt_caching_enabled() -> bool:
    """Prompt-Caching an/aus (Default: an). Zur Laufzeit gelesen, damit
    Tests und Betrieb ohne Neustart umschalten können."""
    raw = os.environ.get("LLM_PROMPT_CACHING", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def fallback_models() -> list[str]:
    """Fallback-Modelle für das OpenRouter-Model-Routing (kommagetrennt).

    Leer = kein Fallback. Hinweis: Ein Fallback-Modell beantwortet im
    Störungsfall studierendensichtbare Chats — Kandidaten vor dem Rollout
    per Tutor-Eval-Vergleich prüfen (siehe toadapt-tutor-response-evaluation).
    """
    raw = os.environ.get("OPENROUTER_FALLBACK_MODELS", "")
    return [model.strip() for model in raw.split(",") if model.strip()]


def build_request_messages(
    system: str | None,
    messages: list[dict[str, str]],
    *,
    cache_system: bool = False,
) -> list[dict]:
    """Baut die Chat-Messages; optional mit Anthropic-Cache-Breakpoint auf
    dem System-Prompt (Inhalt bleibt byte-identisch — nur die Verpackung
    wechselt vom String zum Content-Block)."""
    request_messages: list[dict] = []
    if system:
        if cache_system and prompt_caching_enabled():
            request_messages.append({
                "role": "system",
                "content": [{
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }],
            })
        else:
            request_messages.append({"role": "system", "content": system})
    request_messages.extend(messages)
    return request_messages


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
        cache_system: bool = False,
    ) -> str:
        request_messages = build_request_messages(
            system, messages, cache_system=cache_system
        )

        # OpenRouter-Model-Routing: bei Ausfall/Drosselung des primären
        # Modells wird derselbe Request automatisch ans nächste Modell der
        # Liste geroutet — kein eigener Retry-Code nötig.
        extra_body: dict = {}
        fallbacks = fallback_models()
        if fallbacks:
            extra_body["models"] = [self.model, *fallbacks]

        async with _semaphore():
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=request_messages,
                max_tokens=max_tokens,
                extra_body=extra_body or None,
            )

        served_model = getattr(response, "model", None) or self.model
        usage = getattr(response, "usage", None)
        if usage is not None:
            details = getattr(usage, "prompt_tokens_details", None)
            logger.info(
                "llm_call_completed",
                model=self.model,
                served_model=served_model,
                fallback_used=bool(fallbacks) and served_model != self.model,
                prompt_tokens=getattr(usage, "prompt_tokens", None),
                completion_tokens=getattr(usage, "completion_tokens", None),
                total_tokens=getattr(usage, "total_tokens", None),
                cached_tokens=getattr(details, "cached_tokens", None),
            )

        text = response.choices[0].message.content
        if not text:
            raise RuntimeError("OpenRouter lieferte keine Textantwort")
        return text
