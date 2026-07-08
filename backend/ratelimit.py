"""Einfacher In-Process-Rate-Limiter (Sliding Window).

Bewusst ohne externe Abhängigkeit (Redis o.ä.): Die Limits gelten pro
Worker-Prozess und sind als Kosten-/Missbrauchsbremse gedacht, nicht als
exakte globale Quote. Bei N Workern ist das effektive Limit maximal N-mal
so hoch — für den Schutz von LLM-Kosten und OpenRouter-Quota ausreichend.

Standard-Schlüssel ist die Client-IP (setzt --proxy-headers hinter Railway
voraus); alternativ kann ein Pfad-Parameter (z.B. session_id) als Schlüssel
dienen, damit Studierende hinter Campus-NAT sich nicht gegenseitig drosseln.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status

# Schutz gegen unbegrenztes Wachstum der Key-Map (z.B. IP-Rotation).
_MAX_TRACKED_KEYS = 10_000


def rate_limit(
    times: int,
    seconds: float,
    *,
    scope: str,
    by_path_param: str | None = None,
) -> Callable[[Request], Awaitable[None]]:
    """Erzeugt eine FastAPI-Dependency: max. `times` Aufrufe pro `seconds`."""
    windows: dict[str, deque[float]] = {}

    def _prune(now: float) -> None:
        if len(windows) <= _MAX_TRACKED_KEYS:
            return
        stale = [key for key, q in windows.items() if not q or now - q[-1] > seconds]
        for key in stale:
            windows.pop(key, None)

    async def dependency(request: Request) -> None:
        if by_path_param:
            key = str(request.path_params.get(by_path_param, "unknown"))
        else:
            key = request.client.host if request.client else "unknown"

        now = time.monotonic()
        _prune(now)

        window = windows.setdefault(key, deque())
        while window and now - window[0] > seconds:
            window.popleft()

        if len(window) >= times:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Zu viele Anfragen — bitte einen Moment warten.",
                headers={"Retry-After": str(int(seconds))},
            )
        window.append(now)

    dependency.__name__ = f"rate_limit_{scope}"
    return dependency
