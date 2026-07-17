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

STUDENT_CODE_ENV = "STUDENT_ACCESS_CODE"
STUDENT_CODE_HEADER = "X-Student-Access-Code"

RESEARCH_KEY_ENV = "RESEARCH_API_KEY"


async def require_research_key(
    x_research_key: str | None = Header(default=None, alias="X-Research-Key"),
) -> None:
    """Forschungs-Endpunkte mit Einzelpersonen-Daten (pseudonymisiert).

    BEWUSST ein anderer Key als TOADAPT_API_KEY: Der Teacher-Proxy des
    Frontends kennt nur TOADAPT_API_KEY — Tutor:innen erreichen Einzel-
    profile damit auch technisch nicht (sie sehen nur Gruppen-Aggregate).
    Fail-closed wie require_api_key.
    """
    configured = os.environ.get(RESEARCH_KEY_ENV, "").strip()
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Forschungs-Zugang nicht konfiguriert",
        )
    provided = (x_research_key or "").strip()
    if not provided or not hmac.compare_digest(provided, configured):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültiger oder fehlender Forschungs-Key",
        )


def _configured_student_code() -> str:
    return os.environ.get(STUDENT_CODE_ENV, "").strip()


def student_access_required() -> bool:
    return bool(_configured_student_code())


async def require_student_access(
    x_student_access_code: str | None = Header(default=None, alias=STUDENT_CODE_HEADER),
) -> None:
    """Kohorten-Zugangscode für den Studierenden-Flow.

    Ist STUDENT_ACCESS_CODE nicht gesetzt, bleibt der Flow offen (Dev-/
    Experiment-Modus, z.B. anonyme Prolific-Teilnehmer). Sobald der Code
    gesetzt ist, verlangen alle Studierenden-Endpunkte den Header
    X-Student-Access-Code — sonst kann jeder im Internet LLM-Kosten auslösen.
    """
    configured = _configured_student_code()
    if not configured:
        return

    provided = (x_student_access_code or "").strip()
    if not provided or not hmac.compare_digest(provided, configured):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültiger oder fehlender Zugangscode",
        )


TEACHER_JTI_HEADER = "X-Teacher-Session"


async def reject_revoked_teacher_session(
    x_teacher_session: str | None = Header(default=None, alias=TEACHER_JTI_HEADER),
) -> None:
    """Weist Requests mit einer per Logout widerrufenen Teacher-Session ab.

    Der Teacher-Proxy des Frontends schickt die jti der signierten (und dort
    bereits verifizierten) Session als X-Teacher-Session mit; nach einem
    Logout steht sie auf der Sperrliste → 401. Requests OHNE den Header
    (Forschende/Skripte direkt mit API-Key, Alt-Sessions ohne jti) sind
    bewusst nicht betroffen — deren Auth ist der Key selbst.
    """
    jti = (x_teacher_session or "").strip()
    if not jti:
        return
    from backend.db.revoked_sessions_store import revoked_session_store

    if revoked_session_store.is_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sitzung wurde abgemeldet — bitte neu einloggen",
        )


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
