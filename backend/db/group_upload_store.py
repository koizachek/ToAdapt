"""Store für bewertete Gruppenarbeits-Uploads (Master-Tutor-Upload).

Gleiches Muster wie dashboard_store: Mongo ist die primäre Quelle (überlebt
Railway-Redeploys), die Dateiablage bleibt write-through als Fallback für die
lokale Entwicklung. Fehler beim Mongo-Schreiben werden geloggt, crashen aber
nie den Request.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import structlog

from backend.db import mongo

logger = structlog.get_logger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent / "group_uploads"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


class GroupUploadStore:
    def __init__(self) -> None:
        self.collection_name = os.environ.get(
            "MONGODB_GROUP_UPLOADS_COLLECTION", "group_uploads"
        )

    def save_result(self, result: dict[str, Any]) -> None:
        upload_id = str(result.get("upload_id", ""))

        (RESULTS_DIR / f"{upload_id}.json").write_text(
            json.dumps(result, default=str), encoding="utf-8"
        )

        collection = mongo.get_collection(self.collection_name)
        if collection is None:
            return
        try:
            collection.replace_one(
                {"upload_id": upload_id},
                json.loads(json.dumps(result, default=str)),
                upsert=True,
            )
        except Exception as exc:  # pragma: no cover - external service failure
            logger.warning("group_upload_store_save_failed", upload_id=upload_id, error=str(exc))

    def load_all(self) -> list[dict[str, Any]]:
        collection = mongo.get_collection(self.collection_name)
        if collection is not None:
            try:
                docs = list(collection.find({}, {"_id": 0}))
                if docs:
                    return docs
            except Exception as exc:  # pragma: no cover - external service failure
                logger.warning("group_upload_store_load_failed", error=str(exc))

        results: list[dict[str, Any]] = []
        for f in RESULTS_DIR.glob("*.json"):
            try:
                results.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
        return results

    def get(self, upload_id: str) -> dict[str, Any] | None:
        for result in self.load_all():
            if str(result.get("upload_id", "")) == upload_id:
                return result
        return None


group_upload_store = GroupUploadStore()
