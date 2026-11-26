"""Gemeinsamer LLM-Client für Requesty (OpenAI-kompatibler Router).

Konfiguration über die Umgebung: REQUESTY_API_KEY, REQUESTY_BASE_URL
(Default global; EU: https://router.eu.requesty.ai/v1) und REQUESTY_MODEL.

Härtung für den Betrieb mit vielen gleichzeitigen Nutzern:
- Ein geteilter AsyncOpenAI-Client pro API-Key (Connection-Reuse statt
  Client-pro-Request).
- Timeout und automatische Retries mit exponentiellem Backoff (429/5xx/
  Verbindungsfehler) über die OpenAI-SDK-Mechanik.
- Globales Concurrency-Limit, damit Lastspitzen nicht ungebremst auf
  Requesty durchschlagen.
- Token-Verbrauch wird pro Call geloggt (Kostenmonitoring), inkl. gecachter
  Prompt-Token, sofern der Router sie meldet.
- Prompt-Caching (Anthropic via cache_control): der System-Prompt des Chats
  (Agent-Prompt + kompletter Case, ~3k Token) wird serverseitig gecacht —
  Folge-Turns zahlen dafür nur ~10 % des Input-Preises. Abschaltbar via
  LLM_PROMPT_CACHING=0.
- Fallback-Modelle: Requesty löst den Fallback über eine Fallback-Policy im
  Requesty-Konto. Sie wird als Modell "policy/<name>" in REQUESTY_MODEL
  eingetragen — fällt das primäre Modell aus, routet Requesty denselben
  Request ans nächste Modell der Policy. Hinweis: Ein Fallback-Modell
  beantwortet im Störungsfall studierendensichtbare Chats — Kandidaten vor
  dem Rollout per Tutor-Eval-Vergleich prüfen (siehe
  toadapt-tutor-response-evaluation).
"""

import asyncio
import os

import structlog
from openai import AsyncOpenAI

logger = structlog.get_logger(__name__)

REQUESTY_BASE_URL = (
    os.environ.get("REQUESTY_BASE_URL", "").strip().strip('"\'')
    or "https://router.requesty.ai/v1"
)
DEFAULT_REQUESTY_MODEL = os.environ.get("REQUESTY_MODEL", "").strip() or "mistral/mistral-medium-3-5"

LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "60"))
LLM_MAX_RETRIES = int(os.environ.get("LLM_MAX_RETRIES", "2"))
LLM_MAX_CONCURRENCY = int(os.environ.get("LLM_MAX_CONCURRENCY", "16"))

_shared_clients: dict[str, AsyncOpenAI] = {}
# Semaphoren pro Event-Loop, da asyncio-Primitive an den Loop gebunden sind
# (Tests erzeugen pro Testfall einen neuen Loop).
_semaphores: dict[int, asyncio.Semaphore] = {}


def get_requesty_key() -> str:
    return os.environ.get("REQUESTY_API_KEY", "").strip()


def prompt_caching_enabled() -> bool:
    """Prompt-Caching an/aus (Default: an). Zur Laufzeit gelesen, damit
    Tests und Betrieb ohne Neustart umschalten können."""
    raw = os.environ.get("LLM_PROMPT_CACHING", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


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


def get_requesty_headers() -> dict[str, str]:
    """Optionale Header, die Requesty für die Analytics auswertet."""
    headers: dict[str, str] = {}
    referer = os.environ.get("REQUESTY_HTTP_REFERER", "http://localhost:3000")
    title = os.environ.get("REQUESTY_APP_TITLE", "ToAdapt")

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
            base_url=REQUESTY_BASE_URL,
            default_headers=get_requesty_headers(),
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


class RequestyClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = api_key or get_requesty_key()
        if not key:
            raise ValueError("REQUESTY_API_KEY nicht konfiguriert")

        self.model = model or DEFAULT_REQUESTY_MODEL
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

        async with _semaphore():
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=request_messages,
                max_tokens=max_tokens,
            )

        served_model = getattr(response, "model", None) or self.model
        usage = getattr(response, "usage", None)
        finish_reason = getattr(response.choices[0], "finish_reason", None) if response.choices else None
        if finish_reason == "length":
            # Antwort am max_tokens-Limit abgeschnitten → JSON-Antworten sind
            # dann unvollständig; Aufrufer (Generator) wiederholt mit mehr Budget.
            logger.warning("llm_output_truncated", model=self.model, max_tokens=max_tokens)
        if usage is not None:
            details = getattr(usage, "prompt_tokens_details", None)
            logger.info(
                "llm_call_completed",
                model=self.model,
                served_model=served_model,
                finish_reason=finish_reason,
                prompt_tokens=getattr(usage, "prompt_tokens", None),
                completion_tokens=getattr(usage, "completion_tokens", None),
                total_tokens=getattr(usage, "total_tokens", None),
                cached_tokens=getattr(details, "cached_tokens", None),
            )

        text = response.choices[0].message.content
        if not text:
            raise RuntimeError("Requesty lieferte keine Textantwort")
        return text
