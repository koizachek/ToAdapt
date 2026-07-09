"""Serverseitige Pseudonymisierung von Teilnehmer-Kennungen.

Studierende werden einzeln geloggt (Forschung), aber pseudonymisiert:
Eingegebene Kennungen (Matrikelnummer/Teilnehmer-ID) werden beim Eingang
per HMAC-SHA256 mit einem Server-Secret (PSEUDONYM_SECRET) in ein stabiles
Pseudonym übersetzt — gleiche Eingabe ergibt gleiches Pseudonym (für
Verlaufsdaten nötig), Rückrechnung ist ohne das Secret nicht möglich.

Ist PSEUDONYM_SECRET nicht gesetzt (lokale Entwicklung), bleiben Kennungen
roh — der Startup-Log warnt dann (pseudonymization_enabled=False).
Tutor:innen sehen ohnehin keine Einzelprofile mehr, nur Gruppen-Aggregate.
"""

from __future__ import annotations

import hashlib
import hmac
import os

PSEUDONYM_SECRET_ENV = "PSEUDONYM_SECRET"
PSEUDONYM_PREFIX = "anon-"


def pseudonymization_enabled() -> bool:
    return bool(os.environ.get(PSEUDONYM_SECRET_ENV, "").strip())


def pseudonymize(value: str | None) -> str:
    """Stabiles Pseudonym für eine Teilnehmer-Kennung (idempotent)."""
    raw = (value or "").strip()
    if not raw:
        return ""
    if raw.startswith(PSEUDONYM_PREFIX):
        return raw  # bereits pseudonymisiert (z.B. Retry mit gespeicherter ID)

    secret = os.environ.get(PSEUDONYM_SECRET_ENV, "").strip()
    if not secret:
        return raw

    digest = hmac.new(
        secret.encode("utf-8"), raw.lower().encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"{PSEUDONYM_PREFIX}{digest[:16]}"


def normalize_group_code(value: str | None) -> str:
    """Gruppencodes vereinheitlichen (Selbstauskunft: '12', 'G12', ' g12 ' → 'G12')."""
    raw = (value or "").strip().upper().replace(" ", "")
    if not raw:
        return ""
    if raw.isdigit():
        return f"G{raw}"
    return raw
