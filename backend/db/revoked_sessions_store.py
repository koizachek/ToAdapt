"""Sperrliste widerrufener Teacher-Sessions (Logout-Widerruf).

Der Teacher-Session-Token des Frontends ist stateless signiert — ein Logout
löscht nur das Cookie im Browser. Damit ein kopierter/gestohlener Token nach
dem Logout wirklich ungültig ist, meldet das Frontend seine jti hier ab.
Mongo ist die primäre Ablage; der TTL-Index (Feld expire_at, wie im
Löschkonzept) räumt Einträge automatisch weg, sobald der Token ohnehin
abgelaufen wäre. Zusätzlich hält der Prozess ein In-Memory-Fallback ohne
Mongo (Dev/Single-Worker). Lookup-Fehler sind fail-open: Verfügbarkeit der
Dashboards geht vor, der Widerruf ist eine Härtung on top der 12-h-Ablauffrist.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone

import structlog

from backend.config import retention
from backend.db import mongo

logger = structlog.get_logger(__name__)

# Sperr-Einträge müssen die maximale Token-Gültigkeit (12 h) sicher
# überdauern; danach ist der Token ohnehin abgelaufen.
REVOCATION_TTL = timedelta(hours=24)
_MAX_MEMORY_ENTRIES = 10_000
TTL_INDEX_NAME = "ttl_expire_at"


class RevokedSessionStore:
    def __init__(self) -> None:
        self.collection_name = os.environ.get(
            "MONGODB_REVOKED_SESSIONS_COLLECTION", "revoked_teacher_sessions"
        )
        self._memory: dict[str, float] = {}

    def _prune_memory(self) -> None:
        now = time.monotonic()
        ttl = REVOCATION_TTL.total_seconds()
        if len(self._memory) > _MAX_MEMORY_ENTRIES:
            self._memory = {
                jti: ts for jti, ts in self._memory.items() if now - ts < ttl
            }

    def revoke(self, jti: str) -> bool:
        """Trägt die jti in die Sperrliste ein; True = in Mongo persistiert."""
        self._memory[jti] = time.monotonic()
        self._prune_memory()

        collection = mongo.get_collection(self.collection_name)
        if collection is None:
            logger.warning("teacher_session_revocation_not_persisted", reason="mongo_unavailable")
            return False
        try:
            collection.create_index(
                retention.TTL_FIELD, expireAfterSeconds=0, name=TTL_INDEX_NAME
            )
            now = datetime.now(timezone.utc)
            collection.replace_one(
                {"jti": jti},
                {"jti": jti, "revoked_at": now, retention.TTL_FIELD: now + REVOCATION_TTL},
                upsert=True,
            )
            return True
        except Exception as exc:  # pragma: no cover - external service failure
            logger.warning("teacher_session_revocation_save_failed", error=str(exc))
            return False

    def is_revoked(self, jti: str) -> bool:
        if jti in self._memory:
            return True
        collection = mongo.get_collection(self.collection_name)
        if collection is None:
            return False
        try:
            return collection.find_one({"jti": jti}, {"_id": 1}) is not None
        except Exception as exc:  # pragma: no cover - external service failure
            logger.warning("teacher_session_revocation_lookup_failed", error=str(exc))
            return False


revoked_session_store = RevokedSessionStore()
