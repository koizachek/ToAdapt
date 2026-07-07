"""Shared-Secret-Auth für teacher-/forschungsseitige Endpunkte.

Der Studierenden-Flow (Sessions, Submissions, Lesen approved Cases) bleibt
bewusst offen — Prolific-Teilnehmer sind anonym. Geschützt werden nur:
  - alle /dashboard/*-Endpunkte (enthalten PII: Matrikelnr./Prolific-IDs + Scores)
  - schreibende/kostenverursachende /admin-Endpunkte (Case-Generierung, Approve/Reject)

Der Key wird server-seitig gehalten: Das Next.js-Frontend spricht die
geschützten Endpunkte über einen eigenen Route-Handler-Proxy an, der den
X-API-Key hinzufügt — der Browser sieht ihn nie.
"""

from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException, status

API_KEY_ENV = "TOADAPT_API_KEY"
API_KEY_HEADER = "X-API-Key"


def _configured_key() -> str:
    return os.environ.get(API_KEY_ENV, "").strip()


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Verlangt einen gültigen X-API-Key.

    Fail-closed: Ist kein Key konfiguriert, werden geschützte Endpunkte
    mit 503 abgewiesen, statt sie versehentlich offen zu lassen.
    """
    configured = _configured_key()
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth nicht konfiguriert",
        )

    provided = (x_api_key or "").strip()
    # Konstante-Zeit-Vergleich gegen Timing-Angriffe.
    if not provided or not hmac.compare_digest(provided, configured):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültiger oder fehlender API-Key",
        )
