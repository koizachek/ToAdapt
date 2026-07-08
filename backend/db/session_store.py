"""Persistenter Store für Chat-Sessions.

Sessions lagen bisher nur in einem prozesslokalen Dict — bei Neustart oder
mehreren Workern gingen laufende Sessions verloren. Mit konfiguriertem
MongoDB werden sie jetzt dort persistiert; ohne Mongo bleibt das Verhalten
wie zuvor (nur In-Memory-Cache in den Routes).
"""

from __future__ import annotations

import os

import structlog

from backend.db import mongo
from backend.models.session import Session

logger = structlog.get_logger(__name__)


class SessionStore:
    def __init__(self) -> None:
        self.collection_name = os.environ.get("MONGODB_SESSIONS_COLLECTION", "sessions")

    def save(self, session: Session) -> None:
        collection = mongo.get_collection(self.collection_name)
        if collection is None:
            return
        try:
            collection.replace_one(
                {"session_id": session.session_id},
                session.model_dump(mode="json", exclude_none=True),
                upsert=True,
            )
        except Exception as exc:  # pragma: no cover - external service failure
            logger.warning("session_store_save_failed", session_id=session.session_id, error=str(exc))

    def load(self, session_id: str) -> Session | None:
        collection = mongo.get_collection(self.collection_name)
        if collection is None:
            return None
        try:
            doc = collection.find_one({"session_id": session_id}, {"_id": 0})
            if doc:
                return Session.model_validate(doc)
        except Exception as exc:  # pragma: no cover - external service failure
            logger.warning("session_store_load_failed", session_id=session_id, error=str(exc))
        return None


session_store = SessionStore()
