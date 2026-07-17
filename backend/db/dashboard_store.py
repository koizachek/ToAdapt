"""Store für ausgewertete Submission-Ergebnisse (Dashboard-Quelle).

Bisher landeten die Ergebnisse nur als JSON-Dateien im Container-Dateisystem
— auf Railway gehen sie damit bei jedem Redeploy verloren. Mit konfiguriertem
MongoDB ist Mongo jetzt die primäre Quelle; die Dateiablage bleibt als
Fallback für die lokale Entwicklung.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import structlog

from backend.config import retention
from backend.db import mongo

logger = structlog.get_logger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent / "submissions"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


class DashboardStore:
    def __init__(self) -> None:
        self.collection_name = os.environ.get("MONGODB_DASHBOARD_COLLECTION", "dashboard_results")

    def save_result(self, result: dict[str, Any]) -> None:
        submission_id = str(result.get("submission_id", ""))

        (RESULTS_DIR / f"{submission_id}.json").write_text(
            json.dumps(result, default=str), encoding="utf-8"
        )

        collection = mongo.get_collection(self.collection_name)
        if collection is None:
            return
        doc = json.loads(json.dumps(result, default=str))
        # Nach dem JSON-Roundtrip setzen: der TTL-Index braucht ein echtes
        # BSON-Datum, kein String.
        doc[retention.TTL_FIELD] = retention.formative_expire_at()
        try:
            collection.replace_one(
                {"submission_id": submission_id},
                doc,
                upsert=True,
            )
        except Exception as exc:  # pragma: no cover - external service failure
            logger.warning("dashboard_store_save_failed", submission_id=submission_id, error=str(exc))

    def load_all(self) -> list[dict[str, Any]]:
        collection = mongo.get_collection(self.collection_name)
        if collection is not None:
            try:
                docs = list(collection.find({}, {"_id": 0, retention.TTL_FIELD: 0}))
                if docs:
                    return docs
            except Exception as exc:  # pragma: no cover - external service failure
                logger.warning("dashboard_store_load_failed", error=str(exc))

        results: list[dict[str, Any]] = []
        for f in RESULTS_DIR.glob("*.json"):
            try:
                results.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
        return results


dashboard_store = DashboardStore()
