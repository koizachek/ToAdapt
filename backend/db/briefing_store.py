"""Store für KI-Briefings (Master-Upload → Briefing je Stammgruppe).

Gleiches Muster wie dashboard_store (D3): Mongo ist die primäre Quelle
(überlebt Railway-Redeploys), die Dateiablage bleibt write-through als
Fallback für die lokale Entwicklung. Fehler beim Mongo-Schreiben werden
geloggt, crashen aber nie den Request.

Ein Datensatz enthält den tutor-sichtbaren Teil (``briefing``, Formales)
UND die interne Niveau-Einstufung (``assessment``) — die Trennung erfolgt
in den Routen (``assessment`` nur für den Master).
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

RESULTS_DIR = Path(__file__).resolve().parent / "briefings"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


class BriefingStore:
    def __init__(self) -> None:
        self.collection_name = os.environ.get("MONGODB_BRIEFINGS_COLLECTION", "briefings")

    def save(self, record: dict[str, Any]) -> None:
        briefing_id = str(record.get("briefing_id", ""))
        (RESULTS_DIR / f"{briefing_id}.json").write_text(
            json.dumps(record, default=str, ensure_ascii=False), encoding="utf-8"
        )

        collection = mongo.get_collection(self.collection_name)
        if collection is None:
            return
        doc = json.loads(json.dumps(record, default=str))
        doc[retention.TTL_FIELD] = retention.formative_expire_at()
        try:
            collection.replace_one({"briefing_id": briefing_id}, doc, upsert=True)
        except Exception as exc:  # pragma: no cover - external service failure
            logger.warning("briefing_store_save_failed", briefing_id=briefing_id, error=str(exc))

    def load_all(self) -> list[dict[str, Any]]:
        collection = mongo.get_collection(self.collection_name)
        if collection is not None:
            try:
                docs = list(collection.find({}, {"_id": 0, retention.TTL_FIELD: 0}))
                if docs:
                    return docs
            except Exception as exc:  # pragma: no cover - external service failure
                logger.warning("briefing_store_load_failed", error=str(exc))

        results: list[dict[str, Any]] = []
        for f in RESULTS_DIR.glob("*.json"):
            try:
                results.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
        return results

    def get(self, briefing_id: str) -> dict[str, Any] | None:
        for record in self.load_all():
            if str(record.get("briefing_id", "")) == briefing_id:
                return record
        return None


briefing_store = BriefingStore()
