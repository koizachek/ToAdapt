"""Persistenter Store fuer laufende Submissions."""

from __future__ import annotations

import json
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

from backend.config import retention
from backend.models.submission import Submission

logger = structlog.get_logger(__name__)

RUNTIME_SUBMISSIONS_DIR = Path(__file__).resolve().parent / "runtime_submissions"
RUNTIME_SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)


class SubmissionStore:
    def __init__(self) -> None:
        self.uri = os.environ.get("MONGODB_URI", "").strip()
        self.database_name = os.environ.get("MONGODB_DATABASE", "toadapt")
        self.collection_name = os.environ.get("MONGODB_SUBMISSIONS_COLLECTION", "submission_states")
        self.mas_name = os.environ.get("MONGODB_MAS_NAME", "").strip()
        self.mas_key = os.environ.get("MONGODB_MAS_KEY", "").strip()
        self.host = (
            os.environ.get("MONGODB_HOST", "").strip()
            or os.environ.get("MONGODB_CLUSTER_HOST", "").strip()
            or os.environ.get("MONGODB_CLUSTER", "").strip()
        )
        self._client: MongoClient | None = None
        self._collection = None
        self._last_connection_failure = 0.0

    @property
    def mongo_enabled(self) -> bool:
        return bool((self.uri or (self.mas_name and self.mas_key and self.host)) and MongoClient is not None)

    def _path(self, submission_id: str) -> Path:
        return RUNTIME_SUBMISSIONS_DIR / f"{submission_id}.json"

    def _mongo_uri(self) -> str:
        if self.uri:
            return self.uri
        if not (self.mas_name and self.mas_key and self.host):
            return ""
        return (
            f"mongodb+srv://{quote_plus(self.mas_name)}:{quote_plus(self.mas_key)}"
            f"@{self.host}/{self.database_name}?retryWrites=true&w=majority"
        )

    def _get_collection(self):
        if not self.mongo_enabled:
            return None
        if self._last_connection_failure and time.monotonic() - self._last_connection_failure < 30:
            return None
        if self._collection is None:
            try:
                self._client = MongoClient(self._mongo_uri(), serverSelectionTimeoutMS=2000)
                self._collection = self._client[self.database_name][self.collection_name]
            except Exception as exc:  # pragma: no cover - external service failure
                self._last_connection_failure = time.monotonic()
                logger.warning(
                    "submission_store_connection_failed",
                    error=str(exc),
                    database=self.database_name,
                    collection=self.collection_name,
                )
                return None
        return self._collection

    def save(self, submission: Submission) -> None:
        payload = submission.model_dump(mode="json", exclude_none=True)
        self._path(submission.submission_id).write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

        collection = self._get_collection()
        if collection is None:
            return

        try:
            collection.replace_one(
                {"submission_id": submission.submission_id},
                {**payload, retention.TTL_FIELD: retention.formative_expire_at()},
                upsert=True,
            )
        except Exception as exc:  # pragma: no cover - external service failure
            logger.warning("submission_store_save_failed", submission_id=submission.submission_id, error=str(exc))

    def load(self, submission_id: str) -> Submission | None:
        collection = self._get_collection()
        if collection is not None:
            try:
                doc = collection.find_one({"submission_id": submission_id}, {"_id": 0, retention.TTL_FIELD: 0})
                if doc:
                    return Submission.model_validate(doc)
            except Exception as exc:  # pragma: no cover - external service failure
                logger.warning("submission_store_load_failed", submission_id=submission_id, error=str(exc))

        path = self._path(submission_id)
        if not path.exists():
            return None

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return Submission.model_validate(payload)
        except Exception as exc:
            logger.warning("submission_store_file_load_failed", submission_id=submission_id, error=str(exc))
            return None


submission_store = SubmissionStore()
