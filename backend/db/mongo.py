"""Gemeinsame MongoDB-Verbindung für die Stores.

Ein Client pro Prozess; Collections werden darüber bezogen. Fällt Mongo aus,
liefert get_collection None (mit 30-s-Backoff), die Stores müssen dann auf
ihren Fallback ausweichen. URI-Auflösung identisch zu experiment_logger/
submission_store (MONGODB_URI oder MAS-Credentials + Host).
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from urllib.parse import quote_plus

import structlog
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

try:
    from pymongo import MongoClient
except Exception:  # pragma: no cover - optional dependency at runtime
    MongoClient = None

logger = structlog.get_logger(__name__)

_client: "MongoClient | None" = None
_last_connection_failure = 0.0


def database_name() -> str:
    return os.environ.get("MONGODB_DATABASE", "toadapt")


def resolve_uri() -> str:
    explicit = os.environ.get("MONGODB_URI", "").strip()
    if explicit:
        return explicit

    mas_name = os.environ.get("MONGODB_MAS_NAME", "").strip()
    mas_key = os.environ.get("MONGODB_MAS_KEY", "").strip()
    host = (
        os.environ.get("MONGODB_HOST", "").strip()
        or os.environ.get("MONGODB_CLUSTER_HOST", "").strip()
        or os.environ.get("MONGODB_CLUSTER", "").strip()
    )
    if not (mas_name and mas_key and host):
        return ""

    scheme = os.environ.get("MONGODB_SCHEME", "mongodb+srv")
    options = os.environ.get("MONGODB_OPTIONS", "retryWrites=true&w=majority")
    uri = f"{scheme}://{quote_plus(mas_name)}:{quote_plus(mas_key)}@{host}"
    if database_name():
        uri = f"{uri}/{database_name()}"
    if options:
        uri = f"{uri}?{options}"
    return uri


def mongo_enabled() -> bool:
    return bool(resolve_uri() and MongoClient is not None)


def get_collection(collection_name: str):
    """Liefert die Collection oder None (Mongo nicht konfiguriert/erreichbar)."""
    global _client, _last_connection_failure

    if not mongo_enabled():
        return None
    if _last_connection_failure and time.monotonic() - _last_connection_failure < 30:
        return None

    if _client is None:
        try:
            _client = MongoClient(resolve_uri(), serverSelectionTimeoutMS=2000)
        except Exception as exc:  # pragma: no cover - external service failure
            _last_connection_failure = time.monotonic()
            logger.warning("mongo_connection_failed", error=str(exc))
            return None

    return _client[database_name()][collection_name]
