"""OpenRouter-Stub für Lasttests — imitiert /chat/completions ohne Kosten.

Verwendung (Staging/Lokal, NIE in Produktion):
    .venv/bin/python -m uvicorn scripts.llm_stub:app --port 9500
    # Backend mit: OPENROUTER_BASE_URL=http://127.0.0.1:9500/v1  OPENROUTER_API_KEY=stub

Verhalten:
- Chat-/Formative-Prompts → guardrail-sichere sokratische Frage (Deutsch),
  damit der komplette Pfad inkl. guardrail_check realistisch durchlaufen wird.
- Judge-Prompts (erkannt am JSON-Schema im Prompt) → valides Bewertungs-JSON,
  das parse_evaluation_payload/_score_from_payload akzeptieren.
- Simulierte Latenz: LLM_STUB_LATENCY_MS (Default 1200) ± LLM_STUB_JITTER_MS
  (Default 400) — angelehnt an reale Sonnet-Antwortzeiten für kurze Antworten.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import time

from fastapi import FastAPI, Request

app = FastAPI(title="LLM-Stub (Lasttest)")

LATENCY_MS = int(os.environ.get("LLM_STUB_LATENCY_MS", "1200"))
JITTER_MS = int(os.environ.get("LLM_STUB_JITTER_MS", "400"))

# Guardrail-sicher: endet mit Frage, keine Framework-Namen, keine Empfehlung,
# kein Emoji, kein Slang.
CHAT_REPLY = (
    "Welche Beobachtung aus dem Case stuetzt eure Einschaetzung am staerksten "
    "— und welche Stelle im Text spricht am ehesten dagegen? Wie wuerdet ihr "
    "diesen Widerspruch aufloesen?"
)

JUDGE_REPLY = json.dumps({
    "awarded_points": 13.5,
    "feedback": (
        "Die Argumentationslinie ist erkennbar und nutzt Case-Belege. "
        "Welche Konsequenz folgt aus eurer Entscheidung fuer die naechsten "
        "Schritte des Unternehmens?"
    ),
    "learning_objective_tags": ["analyse", "transfer"],
    "canvas_alignment_score": 0.6,
    "addressed_canvas_blocks": ["value_propositions"],
    "missing_canvas_blocks": ["cost_structure"],
    "canvas_rationale": "Teilweise fallbezogen angewendet.",
    "judge_confidence": "high",
    "score_band": "solid",
    "main_strengths": ["Klarer Case-Bezug"],
    "main_penalties": ["Konsequenzen bleiben implizit"],
    "needs_human_review": False,
})


def _is_judge_prompt(messages: list[dict]) -> bool:
    text = " ".join(str(m.get("content", "")) for m in messages)
    return "Antworte mit einem JSON-Objekt" in text


@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def chat_completions(request: Request) -> dict:
    body = await request.json()
    messages = body.get("messages", [])

    delay = max(0.0, (LATENCY_MS + random.uniform(-JITTER_MS, JITTER_MS)) / 1000.0)
    await asyncio.sleep(delay)

    content = JUDGE_REPLY if _is_judge_prompt(messages) else CHAT_REPLY
    prompt_chars = sum(len(str(m.get("content", ""))) for m in messages)

    return {
        "id": f"stub-{time.time_ns()}",
        "object": "chat.completion",
        "model": body.get("model", "stub"),
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": prompt_chars // 4,
            "completion_tokens": len(content) // 4,
            "total_tokens": prompt_chars // 4 + len(content) // 4,
        },
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "latency_ms": LATENCY_MS, "jitter_ms": JITTER_MS}
