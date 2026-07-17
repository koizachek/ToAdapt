"""Tests für das Löschkonzept: expire_at in allen Mongo-Schreibpfaden + TTL-Skript.

Umsetzung des Datenschutzantrags (Teil 1 Abschnitt 7, Teil 2 Abschnitt 5):
formative Stores schreiben den formativen Löschtermin, das Forschungslog den
Forschungs-Löschtermin; scripts/ensure_mongo_indexes.py legt TTL-Indizes an
und trägt expire_at bei Bestandsdokumenten nach.
"""

from datetime import datetime, timezone

import backend.db.mongo as mongo_module
from backend.config import retention
from backend.db.dashboard_store import DashboardStore
from backend.db.experiment_logger import experiment_logger
from backend.db.group_upload_store import GroupUploadStore
from backend.db.session_store import SessionStore
from backend.db.submission_store import SubmissionStore
from backend.models.session import Session
from backend.models.submission import Submission, SubmissionStatus
from scripts.ensure_mongo_indexes import (
    TTL_INDEX_NAME,
    collection_plan,
    ensure_lookup_indexes,
    ensure_ttl,
)


class FakeUpdateResult:
    def __init__(self, modified_count: int) -> None:
        self.modified_count = modified_count


class FakeCollection:
    def __init__(self, missing: int = 0, indexes: dict | None = None) -> None:
        self.replaced: list[tuple[dict, dict]] = []
        self.inserted: list[dict] = []
        self.projections: list[dict] = []
        self.created_indexes: list[tuple[str, dict]] = []
        self.update_calls: list[tuple[dict, dict]] = []
        self._missing = missing
        self._indexes = indexes or {"_id_": {"key": [("_id", 1)]}}

    def replace_one(self, flt, doc, upsert=False):
        self.replaced.append((flt, doc))

    def insert_one(self, doc):
        self.inserted.append(doc)

    def find_one(self, flt, projection=None):
        self.projections.append(projection)
        return None

    def find(self, flt, projection=None):
        self.projections.append(projection)
        return []

    def count_documents(self, flt):
        return self._missing

    def index_information(self):
        return self._indexes

    def create_index(self, field, **options):
        self.created_indexes.append((field, options))

    def update_many(self, flt, update):
        self.update_calls.append((flt, update))
        return FakeUpdateResult(self._missing)


# ---------------------------------------------------------------------------
# Fristen-Konfiguration
# ---------------------------------------------------------------------------

def test_default_deadlines(monkeypatch):
    monkeypatch.delenv("RETENTION_FORMATIVE_EXPIRE_AT", raising=False)
    monkeypatch.delenv("RETENTION_RESEARCH_EXPIRE_AT", raising=False)
    assert retention.formative_expire_at() == datetime(2027, 1, 31, tzinfo=timezone.utc)
    assert retention.research_expire_at() == datetime(2028, 12, 31, tzinfo=timezone.utc)


def test_env_override_iso_date(monkeypatch):
    monkeypatch.setenv("RETENTION_FORMATIVE_EXPIRE_AT", "2027-03-01")
    assert retention.formative_expire_at() == datetime(2027, 3, 1, tzinfo=timezone.utc)


def test_invalid_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("RETENTION_RESEARCH_EXPIRE_AT", "kein-datum")
    assert retention.research_expire_at() == retention.DEFAULT_RESEARCH_EXPIRE_AT


# ---------------------------------------------------------------------------
# Schreibpfade: alle Stores setzen expire_at als echtes Datum
# ---------------------------------------------------------------------------

def _make_session() -> Session:
    return Session(session_id="s-1", user_id="anon-1", case_id="case-1", tp_phase=1)


def test_session_store_writes_formative_expire_at(monkeypatch):
    fake = FakeCollection()
    monkeypatch.setattr(mongo_module, "get_collection", lambda name: fake)
    SessionStore().save(_make_session())

    _, doc = fake.replaced[0]
    assert isinstance(doc[retention.TTL_FIELD], datetime)
    assert doc[retention.TTL_FIELD] == retention.formative_expire_at()


def test_session_store_load_excludes_expire_at(monkeypatch):
    fake = FakeCollection()
    monkeypatch.setattr(mongo_module, "get_collection", lambda name: fake)
    SessionStore().load("s-1")
    assert fake.projections[0][retention.TTL_FIELD] == 0


def test_submission_store_writes_formative_expire_at(monkeypatch, tmp_path):
    import backend.db.submission_store as submission_module

    monkeypatch.setattr(submission_module, "RUNTIME_SUBMISSIONS_DIR", tmp_path)
    store = SubmissionStore()
    fake = FakeCollection()
    monkeypatch.setattr(store, "_get_collection", lambda: fake)

    submission = Submission(
        submission_id="sub-1",
        user_id="anon-1",
        matrikelnummer="anon-1",
        case_id="case-1",
        target_tp=1,
        status=SubmissionStatus.IN_PROGRESS,
    )
    store.save(submission)

    _, doc = fake.replaced[0]
    assert doc[retention.TTL_FIELD] == retention.formative_expire_at()
    # Datei-Fallback bleibt frei von expire_at (nur Mongo löscht per TTL).
    assert retention.TTL_FIELD not in (tmp_path / "sub-1.json").read_text(encoding="utf-8")


def test_dashboard_store_writes_formative_expire_at(monkeypatch, tmp_path):
    import backend.db.dashboard_store as dashboard_module

    monkeypatch.setattr(dashboard_module, "RESULTS_DIR", tmp_path)
    fake = FakeCollection()
    monkeypatch.setattr(mongo_module, "get_collection", lambda name: fake)

    DashboardStore().save_result({"submission_id": "sub-1", "score": 10})

    _, doc = fake.replaced[0]
    assert isinstance(doc[retention.TTL_FIELD], datetime)
    assert doc[retention.TTL_FIELD] == retention.formative_expire_at()


def test_group_upload_store_writes_formative_expire_at(monkeypatch, tmp_path):
    import backend.db.group_upload_store as group_module

    monkeypatch.setattr(group_module, "RESULTS_DIR", tmp_path)
    fake = FakeCollection()
    monkeypatch.setattr(mongo_module, "get_collection", lambda name: fake)

    GroupUploadStore().save_result({"upload_id": "up-1", "group_code": "G1"})

    _, doc = fake.replaced[0]
    assert doc[retention.TTL_FIELD] == retention.formative_expire_at()


def test_experiment_logger_writes_research_expire_at(monkeypatch):
    fake = FakeCollection()
    monkeypatch.setattr(experiment_logger, "_get_collection", lambda: fake)

    experiment_logger.log_event("unit_test_event", {"k": "v"})

    doc = fake.inserted[0]
    assert doc[retention.TTL_FIELD] == retention.research_expire_at()
    # Forschungsfrist ist bewusst länger als die formative Frist.
    assert retention.research_expire_at() > retention.formative_expire_at()


# ---------------------------------------------------------------------------
# scripts/ensure_mongo_indexes.py
# ---------------------------------------------------------------------------

def test_collection_plan_maps_research_deadline_to_events(monkeypatch):
    monkeypatch.delenv("RETENTION_FORMATIVE_EXPIRE_AT", raising=False)
    monkeypatch.delenv("RETENTION_RESEARCH_EXPIRE_AT", raising=False)
    plan = dict(collection_plan())
    assert plan["experiment_events"] == retention.research_expire_at()
    for name in ("sessions", "submission_states", "dashboard_results", "group_uploads"):
        assert plan[name] == retention.formative_expire_at()


def test_ensure_ttl_dry_run_writes_nothing():
    fake = FakeCollection(missing=5)
    info = ensure_ttl(fake, retention.formative_expire_at(), dry_run=True)
    assert info == {"missing_expire_at": 5, "index_exists": False, "changed": False}
    assert fake.created_indexes == []
    assert fake.update_calls == []


def test_ensure_ttl_creates_index_and_backfills():
    deadline = retention.formative_expire_at()
    fake = FakeCollection(missing=3)
    info = ensure_ttl(fake, deadline, dry_run=False)

    field, options = fake.created_indexes[0]
    assert field == retention.TTL_FIELD
    assert options == {"expireAfterSeconds": 0, "name": TTL_INDEX_NAME}

    flt, update = fake.update_calls[0]
    assert flt == {retention.TTL_FIELD: {"$exists": False}}
    assert update == {"$set": {retention.TTL_FIELD: deadline}}
    assert info["backfilled"] == 3


def test_ensure_ttl_skips_existing_index():
    fake = FakeCollection(
        missing=0,
        indexes={TTL_INDEX_NAME: {"key": [(retention.TTL_FIELD, 1)], "expireAfterSeconds": 0}},
    )
    ensure_ttl(fake, retention.formative_expire_at(), dry_run=False)
    assert fake.created_indexes == []
    assert fake.update_calls == []


def test_ensure_lookup_indexes_creates_missing_fields():
    fake = FakeCollection()
    created = ensure_lookup_indexes(fake, ["submission_id", "group_code"], dry_run=False)
    assert created == ["submission_id", "group_code"]
    assert fake.created_indexes == [
        ("submission_id", {"name": "idx_submission_id"}),
        ("group_code", {"name": "idx_group_code"}),
    ]


def test_ensure_lookup_indexes_skips_existing_and_dry_run():
    fake = FakeCollection(
        indexes={
            "_id_": {"key": [("_id", 1)]},
            "idx_session_id": {"key": [("session_id", 1)]},
        }
    )
    assert ensure_lookup_indexes(fake, ["session_id"], dry_run=False) == []

    fake_dry = FakeCollection()
    assert ensure_lookup_indexes(fake_dry, ["session_id"], dry_run=True) == ["session_id"]
    assert fake_dry.created_indexes == []
