"""Batch-Verarbeitung der Briefing-Uploads (asynchron, mit Statusdokument).

Ein Semester-Upload (bis 440 Abgaben à ~20 s LLM-Zeit, 8 parallel) dauert
deutlich länger als jeder HTTP-Timeout zwischen Browser, Vercel und Railway.
Deshalb nimmt ``POST /briefings/upload`` das ZIP entgegen, validiert es,
legt ein Batch-Dokument an und verarbeitet die Einträge in einem
Hintergrund-Task des Event-Loops. Der Fortschritt wird ins Batch-Dokument
geschrieben (Store nach D3-Muster: Mongo primär, Datei-Fallback), das
Frontend pollt ``GET /briefings/batches/{batch_id}``.

Grenzen (bewusst akzeptiert): Der Task lebt im Worker-Prozess. Stirbt der
Prozess (Redeploy) mitten im Batch, bleibt das Dokument auf ``running`` —
das Frontend meldet Batches ohne Fortschritt seit STALE_AFTER_SECONDS als
abgebrochen; ein erneuter Upload überschreibt die betroffenen Stammgruppen
(neuester Datensatz gewinnt).
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from backend.config import retention
from backend.db import mongo
from backend.timeutils import naive_utcnow

logger = structlog.get_logger(__name__)

BATCH_DIR = Path(__file__).resolve().parent.parent / "db" / "briefings" / "batches"
BATCH_DIR.mkdir(parents=True, exist_ok=True)

STALE_AFTER_SECONDS = 30 * 60

# Laufende Tasks pro Prozess — verhindert, dass der Garbage Collector einen
# create_task()-Task einsammelt, bevor er fertig ist.
_running_tasks: set[asyncio.Task] = set()


class BatchStore:
    def __init__(self) -> None:
        self.collection_name = os.environ.get("MONGODB_BRIEFING_BATCHES_COLLECTION", "briefing_batches")

    def save(self, batch: dict[str, Any]) -> None:
        batch_id = str(batch.get("batch_id", ""))
        (BATCH_DIR / f"{batch_id}.json").write_text(
            json.dumps(batch, default=str, ensure_ascii=False), encoding="utf-8"
        )
        collection = mongo.get_collection(self.collection_name)
        if collection is None:
            return
        doc = json.loads(json.dumps(batch, default=str))
        doc[retention.TTL_FIELD] = retention.formative_expire_at()
        try:
            collection.replace_one({"batch_id": batch_id}, doc, upsert=True)
        except Exception as exc:  # pragma: no cover - external service failure
            logger.warning("briefing_batch_store_save_failed", batch_id=batch_id, error=str(exc))

    def load_all(self) -> list[dict[str, Any]]:
        collection = mongo.get_collection(self.collection_name)
        if collection is not None:
            try:
                docs = list(collection.find({}, {"_id": 0, retention.TTL_FIELD: 0}))
                if docs:
                    return docs
            except Exception as exc:  # pragma: no cover - external service failure
                logger.warning("briefing_batch_store_load_failed", error=str(exc))
        results: list[dict[str, Any]] = []
        for f in BATCH_DIR.glob("*.json"):
            try:
                results.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
        return results

    def get(self, batch_id: str) -> dict[str, Any] | None:
        for batch in self.load_all():
            if str(batch.get("batch_id", "")) == batch_id:
                return batch
        return None


batch_store = BatchStore()


def new_batch(*, batch_id: str, target_tp: int, total: int, uploaded_by: str | None, filename: str) -> dict:
    now = naive_utcnow().isoformat()
    return {
        "batch_id": batch_id,
        "target_tp": target_tp,
        "status": "running",          # running | done | failed
        "filename": filename,
        "total": total,
        "processed": 0,
        "briefed": 0,
        "unassigned": 0,
        "failed": 0,
        "review": 0,
        "uploaded_by": uploaded_by,
        "started_at": now,
        "updated_at": now,
        "finished_at": None,
        "error": None,
    }


def is_stale(batch: dict, now: datetime | None = None) -> bool:
    if batch.get("status") != "running":
        return False
    try:
        updated = datetime.fromisoformat(str(batch.get("updated_at")))
    except ValueError:
        return True
    return ((now or naive_utcnow()) - updated).total_seconds() > STALE_AFTER_SECONDS


def with_stale_flag(batch: dict) -> dict:
    out = dict(batch)
    out["stale"] = is_stale(batch)
    return out


async def run_batch(
    batch: dict,
    entries: list[tuple[str, bytes]],
    process: Callable[[str, bytes], Awaitable[dict]],
    *,
    concurrency: int,
    save_record: Callable[[dict], None],
) -> dict:
    """Verarbeitet alle Einträge mit begrenzter Parallelität und schreibt den
    Fortschritt nach jedem Eintrag ins Batch-Dokument. ``process`` liefert
    einen Datensatz (dict) und darf keine Exception werfen; tut sie es doch,
    zählt der Eintrag als failed und der Batch läuft weiter."""
    gate = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()

    async def _one(filename: str, payload: bytes) -> None:
        async with gate:
            try:
                record = await process(filename, payload)
            except Exception as exc:  # pragma: no cover - Sicherheitsnetz
                logger.error("briefing_batch_entry_crashed", batch_id=batch["batch_id"], filename=filename, error=str(exc))
                record = None
        async with lock:
            batch["processed"] += 1
            if record is None or record.get("status") == "extraction_failed":
                batch["failed"] += 1
            else:
                if record.get("status") == "briefed":
                    batch["briefed"] += 1
                if not (record.get("ueg") and record.get("sg")):
                    batch["unassigned"] += 1
            if record is not None:
                if record.get("needs_human_review"):
                    batch["review"] += 1
                await asyncio.to_thread(save_record, record)
            batch["updated_at"] = naive_utcnow().isoformat()
            await asyncio.to_thread(batch_store.save, batch)

    try:
        await asyncio.gather(*(_one(name, payload) for name, payload in entries))
        batch["status"] = "done"
    except Exception as exc:  # pragma: no cover - Sicherheitsnetz
        batch["status"] = "failed"
        batch["error"] = str(exc)
        logger.error("briefing_batch_failed", batch_id=batch["batch_id"], error=str(exc))
    batch["finished_at"] = naive_utcnow().isoformat()
    batch["updated_at"] = batch["finished_at"]
    await asyncio.to_thread(batch_store.save, batch)
    logger.info(
        "briefing_batch_processed",
        batch_id=batch["batch_id"],
        target_tp=batch["target_tp"],
        total=batch["total"],
        briefed=batch["briefed"],
        unassigned=batch["unassigned"],
        failed=batch["failed"],
        review=batch["review"],
        uploaded_by=batch.get("uploaded_by"),
        status=batch["status"],
    )
    return batch


def start_background(coro: Awaitable) -> asyncio.Task:
    task = asyncio.ensure_future(coro)
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)
    return task
