"""Download-Protokoll der Briefing- und Feedback-Dokumente (Master-Monitoring).

Owner-Entscheidung 2026-09-13: Der Master sieht, wer wann hoch- UND
heruntergeladen hat. Gespeichert wird pro Download nur: Konto des
Übungsgruppenleiters, Zeitpunkt, Touchpoint, Art (briefing | feedback),
Umfang (bundle | single) und ggf. der Gruppencode. Keine Studierendendaten,
keine Dateiinhalte.

Muster D3: Mongo primär (Collection briefing_downloads), Datei-Fallback
write-through; Fehler werden geloggt, nie an den Request durchgereicht.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

import structlog

from backend.config import retention
from backend.db import mongo
from backend.timeutils import naive_utcnow

logger = structlog.get_logger(__name__)

DOWNLOADS_DIR = Path(__file__).resolve().parent / "briefings" / "downloads"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)


class DownloadLogStore:
    def __init__(self) -> None:
        self.collection_name = os.environ.get("MONGODB_BRIEFING_DOWNLOADS_COLLECTION", "briefing_downloads")

    def log(
        self,
        *,
        tutor: str | None,
        target_tp: int,
        kind: str,
        scope: str,
        code: str | None = None,
        briefing_id: str | None = None,
    ) -> dict[str, Any]:
        event = {
            "download_id": str(uuid.uuid4()),
            "tutor": tutor or "operator",
            "target_tp": int(target_tp),
            "kind": kind,            # briefing | feedback
            "scope": scope,          # bundle | single
            "code": code,
            "briefing_id": briefing_id,
            "at": naive_utcnow().isoformat(),
        }
        try:
            (DOWNLOADS_DIR / f"{event['download_id']}.json").write_text(
                json.dumps(event, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as exc:  # pragma: no cover - FS failure
            logger.warning("download_log_file_failed", error=str(exc))
        collection = mongo.get_collection(self.collection_name)
        if collection is not None:
            doc = dict(event)
            doc[retention.TTL_FIELD] = retention.formative_expire_at()
            try:
                collection.insert_one(doc)
            except Exception as exc:  # pragma: no cover - external service failure
                logger.warning("download_log_save_failed", error=str(exc))
        logger.info("briefing_downloaded", **{k: v for k, v in event.items() if k != "download_id"})
        return event

    def load_all(self) -> list[dict[str, Any]]:
        collection = mongo.get_collection(self.collection_name)
        if collection is not None:
            try:
                docs = list(collection.find({}, {"_id": 0, retention.TTL_FIELD: 0}))
                if docs:
                    return docs
            except Exception as exc:  # pragma: no cover - external service failure
                logger.warning("download_log_load_failed", error=str(exc))
        out: list[dict[str, Any]] = []
        for f in DOWNLOADS_DIR.glob("*.json"):
            try:
                out.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
        return out


download_log = DownloadLogStore()
