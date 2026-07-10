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
import re

PSEUDONYM_SECRET_ENV = "PSEUDONYM_SECRET"
PSEUDONYM_PREFIX = "anon-"

GROUP_CODE_MAX_ENV = "GROUP_CODE_MAX"
_GROUP_CODE_PATTERN = re.compile(r"^G([1-9]\d{0,3})$")


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


def group_code_max() -> int:
    """Höchste gültige Gruppennummer (Env GROUP_CODE_MAX); 0 = Validierung aus."""
    raw = os.environ.get(GROUP_CODE_MAX_ENV, "").strip()
    try:
        return max(0, int(raw)) if raw else 0
    except ValueError:
        return 0


def group_code_allowed(normalized: str) -> bool:
    """Prüft einen (bereits normalisierten) Gruppencode gegen das Kurs-Schema.

    Mit GROUP_CODE_MAX=360 sind genau G1–G360 gültig — Tippfehler wie 'G520'
    oder Freitext ('TEAMA') werden beim Login abgefangen, statt später als
    Phantom-Gruppen im Tutor-Dashboard und beim Matching der Gruppenarbeits-
    Uploads aufzutauchen. Ohne gesetztes GROUP_CODE_MAX (Default, auch für
    Prolific-Läufe) ist jede Selbstauskunft erlaubt. Ein leerer Code gilt
    als erlaubt — ob eine Gruppe Pflicht ist, entscheidet der Login-Flow.
    """
    limit = group_code_max()
    if limit <= 0 or not normalized:
        return True
    match = _GROUP_CODE_PATTERN.match(normalized)
    return bool(match) and int(match.group(1)) <= limit
