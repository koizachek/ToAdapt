"""Aufbewahrungsfristen gemäß Datenschutzantrag (Teil 1 Lehrbetrieb, Teil 2 Forschung).

Formative Lehrbetriebs-Daten (sessions, submission_states, dashboard_results,
group_uploads) werden zum festen Termin Semesterende + 4 Wochen gelöscht; das
Forschungslog (experiment_events) längstens 24 Monate nach Semesterende. Die
Löschung übernimmt MongoDB über einen TTL-Index (expireAfterSeconds=0) auf dem
Feld `expire_at`, das die Stores bei jedem Schreiben setzen. Indizes und
Backfill für Bestandsdokumente: scripts/ensure_mongo_indexes.py.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger(__name__)

TTL_FIELD = "expire_at"

# Defaults für den Kursdurchlauf HS 2026 (Quelle: Datenschutzantrag Teil 1,
# Abschnitt 7 bzw. Teil 2, Abschnitt 5, Stand 2026-07-17). Für einen neuen
# Durchlauf per Env überschreiben oder hier nachziehen.
DEFAULT_FORMATIVE_EXPIRE_AT = datetime(2027, 1, 31, tzinfo=timezone.utc)
DEFAULT_RESEARCH_EXPIRE_AT = datetime(2028, 12, 31, tzinfo=timezone.utc)


def _expire_at_from_env(env_key: str, default: datetime) -> datetime:
    raw = os.environ.get(env_key, "").strip()
    if not raw:
        return default
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        logger.warning("retention_env_invalid", env_key=env_key, value=raw)
        return default
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def formative_expire_at() -> datetime:
    """Löschtermin für formative Lehrbetriebs-Daten (Semesterende + 4 Wochen)."""
    return _expire_at_from_env("RETENTION_FORMATIVE_EXPIRE_AT", DEFAULT_FORMATIVE_EXPIRE_AT)


def research_expire_at() -> datetime:
    """Löschtermin für das Forschungslog (längstens 24 Monate nach Semesterende)."""
    return _expire_at_from_env("RETENTION_RESEARCH_EXPIRE_AT", DEFAULT_RESEARCH_EXPIRE_AT)
