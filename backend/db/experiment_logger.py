"""Optionales MongoDB-Logging für Experimental-Runs."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import structlog
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

try:
    from pymongo import MongoClient
    from pymongo.collection import Collection
except Exception:  # pragma: no cover - optional dependency at runtime
    MongoClient = None
    Collection = Any

logger = structlog.get_logger(__name__)


class MongoExperimentLogger:
    def __init__(self) -> None:
        self.mas_name = os.environ.get("MONGODB_MAS_NAME", "").strip()
        self.mas_key = os.environ.get("MONGODB_MAS_KEY", "").strip()
        self.uri = self._resolve_uri()
        self.database_name = os.environ.get("MONGODB_DATABASE", "toadapt")
        self.collection_name = os.environ.get("MONGODB_COLLECTION", "experiment_events")
        self._client: MongoClient | None = None
        self._collection: Collection | None = None
        self._last_connection_failure = 0.0

        if self.uri and MongoClient is None:
            logger.warning("mongo_logger_unavailable", reason="pymongo_not_installed")

    @property
    def enabled(self) -> bool:
        return bool(self.uri and MongoClient is not None)

    @property
    def connection_mode(self) -> str:
        if os.environ.get("MONGODB_URI", "").strip():
            return "uri"
        if self.uri:
            return "mas_credentials"
        return "disabled"

    def _resolve_uri(self) -> str:
        explicit_uri = os.environ.get("MONGODB_URI", "").strip()
        if explicit_uri:
            return explicit_uri

        host = (
            os.environ.get("MONGODB_HOST", "").strip()
            or os.environ.get("MONGODB_CLUSTER_HOST", "").strip()
            or os.environ.get("MONGODB_CLUSTER", "").strip()
        )
        if not (self.mas_name and self.mas_key and host):
            return ""

        scheme = os.environ.get("MONGODB_SCHEME", "mongodb+srv")
        options = os.environ.get("MONGODB_OPTIONS", "retryWrites=true&w=majority")
        database = os.environ.get("MONGODB_DATABASE", "toadapt").strip()

        username = quote_plus(self.mas_name)
        password = quote_plus(self.mas_key)
        uri = f"{scheme}://{username}:{password}@{host}"

        if database:
            uri = f"{uri}/{database}"

        if options:
            uri = f"{uri}?{options}"

        return uri

    def _get_collection(self) -> Collection | None:
        if not self.enabled:
            return None
        if self._last_connection_failure and time.monotonic() - self._last_connection_failure < 30:
            return None

        if self._collection is None:
            try:
                self._client = MongoClient(self.uri, serverSelectionTimeoutMS=2000)
                self._collection = self._client[self.database_name][self.collection_name]
            except Exception as exc:  # pragma: no cover - external service failure
                self._last_connection_failure = time.monotonic()
                logger.warning(
                    "mongo_log_connection_failed",
                    error=str(exc),
                    database=self.database_name,
                    collection=self.collection_name,
                )
                return None

        return self._collection

    def log_event(self, event_type: str, payload: dict[str, Any]) -> None:
        collection = self._get_collection()
        if collection is None:
            return

        try:
            collection.insert_one({
                "event_type": event_type,
                "created_at": datetime.now(timezone.utc),
                "payload": payload,
            })
        except Exception as exc:  # pragma: no cover - external service failure
            logger.warning(
                "mongo_log_failed",
                event_type=event_type,
                error=str(exc),
                database=self.database_name,
                collection=self.collection_name,
            )


experiment_logger = MongoExperimentLogger()
