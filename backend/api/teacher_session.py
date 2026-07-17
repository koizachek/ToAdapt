"""Widerruf von Teacher-Sessions (Logout-Härtung).

Der Logout-Handler des Frontends meldet hier die jti des signierten
Session-Tokens ab; danach weist reject_revoked_teacher_session (backend/auth.py)
jeden Proxy-Request mit diesem Token ab — auch wenn der Token selbst noch
nicht abgelaufen ist (gestohlenes/kopiertes Cookie).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.auth import require_api_key
from backend.db.revoked_sessions_store import revoked_session_store
from backend.ratelimit import rate_limit

router = APIRouter(
    prefix="/auth/teacher-session",
    tags=["auth"],
    dependencies=[Depends(require_api_key)],
)


class RevokeRequest(BaseModel):
    jti: str = Field(min_length=8, max_length=128)


@router.post("/revoke", dependencies=[Depends(rate_limit(30, 60, scope="teacher_revoke"))])
async def revoke_teacher_session(body: RevokeRequest) -> dict:
    persisted = revoked_session_store.revoke(body.jti)
    # persisted=False heißt: nur im Prozess-Speicher gesperrt (kein Mongo) —
    # der Logout funktioniert trotzdem, überlebt aber keinen Worker-Neustart.
    return {"revoked": True, "persisted": persisted}
