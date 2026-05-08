"""Gemeinsamer LLM-Client für OpenRouter."""

import os

from openai import AsyncOpenAI

OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
DEFAULT_OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")


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


class OpenRouterClient:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = api_key or get_openrouter_key()
        if not key:
            raise ValueError("OPENROUTER_API_KEY nicht konfiguriert")

        self.model = model or DEFAULT_OPENROUTER_MODEL
        self.client = AsyncOpenAI(
            api_key=key,
            base_url=OPENROUTER_BASE_URL,
            default_headers=get_openrouter_headers(),
        )

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

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=request_messages,
            max_tokens=max_tokens,
        )

        text = response.choices[0].message.content
        if not text:
            raise RuntimeError("OpenRouter lieferte keine Textantwort")
        return text
