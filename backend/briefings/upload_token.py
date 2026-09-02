"""Kurzlebige Upload-Tokens für den Direkt-Upload Browser → Backend.

Vercel begrenzt Request-Bodies von Serverless-/Route-Handlern auf 4,5 MB —
ein Semester-ZIP mit hunderten PPTX-Abgaben passt nicht durch den
Teacher-Proxy. Deshalb holt sich der Browser beim Frontend ein signiertes,
kurzlebiges Token (nur mit gültiger Master-Session) und schickt das ZIP
direkt an Railway (``POST /briefings/upload`` mit ``X-Upload-Token``).

Signatur: HMAC-SHA256 über die Base64url-Payload, Schlüssel = TOADAPT_API_KEY
(kennen beide Seiten bereits; kein zusätzliches Secret nötig). Payload:
``{"exp": <unix>, "tutor": "...", "master": true, "jti": "..."}``. Das Token
ersetzt NUR auf der Upload-Route den X-API-Key; es ist auf ``master`` und
eine Lebensdauer von höchstens MAX_TTL_SECONDS beschränkt und respektiert
die jti-Sperrliste (Logout).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid

from backend.auth import API_KEY_ENV

UPLOAD_TOKEN_HEADER = "X-Upload-Token"
DEFAULT_TTL_SECONDS = 15 * 60
MAX_TTL_SECONDS = 60 * 60


class UploadTokenError(ValueError):
    pass


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _secret() -> bytes:
    key = os.environ.get(API_KEY_ENV, "").strip()
    if not key:
        raise UploadTokenError("Auth nicht konfiguriert")
    return key.encode("utf-8")


def sign_upload_token(*, tutor: str, master: bool, jti: str | None = None, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> str:
    """Erzeugt ein Token (Backend-Seite; das Frontend implementiert dieselbe
    Signatur mit Web Crypto — siehe frontend/app/api/teacher/upload-token)."""
    payload = {
        "exp": int(time.time()) + min(int(ttl_seconds), MAX_TTL_SECONDS),
        "tutor": tutor,
        "master": bool(master),
        "jti": jti or str(uuid.uuid4()),
    }
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = _b64url(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_upload_token(token: str | None) -> dict:
    """Prüft Signatur, Ablauf und Master-Flag; liefert die Payload oder wirft
    UploadTokenError."""
    if not token or "." not in token:
        raise UploadTokenError("Upload-Token fehlt")
    body, sig = token.strip().split(".", 1)
    expected = _b64url(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise UploadTokenError("Upload-Token ungültig")
    try:
        payload = json.loads(_b64url_decode(body))
    except (ValueError, json.JSONDecodeError) as exc:
        raise UploadTokenError("Upload-Token ungültig") from exc
    exp = int(payload.get("exp", 0) or 0)
    if exp <= 0 or exp > int(time.time()) + MAX_TTL_SECONDS or exp < int(time.time()):
        raise UploadTokenError("Upload-Token abgelaufen")
    if payload.get("master") is not True:
        raise UploadTokenError("Nur für den Master-Tutor")
    return payload
