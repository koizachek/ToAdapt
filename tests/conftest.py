"""Test-Isolation: Kein Test darf die echte MongoDB erreichen.

Die Store-Module laden die Root-.env beim Import — lokal stehen dort die
PRODUKTIONS-Credentials (Atlas). Ohne diese Fixture schreiben Testläufe echte
Sessions/Submissions/Events in die Produktions-Collections (passiert am
2026-07-17: 32 Test-Events im Forschungslog, gleicher Mechanismus wie die
find_dotenv-Falle beim Lasttest am 2026-07-10). CI ist davon nie betroffen
(keine Mongo-Secrets in Actions) — das Leck existiert nur lokal.

Die Fixture räumt die MONGODB_*-Env pro Test weg UND neutralisiert die beim
Import bereits initialisierten Singletons (experiment_logger, submission_store,
mongo._client), die die Env in __init__ gelesen haben. Tests, die Mongo-Pfade
prüfen wollen, patchen wie bisher gezielt (FakeCollection / monkeypatch).
"""

import os

import pytest

import backend.db.mongo as mongo_module
from backend.db.experiment_logger import experiment_logger
from backend.db.submission_store import submission_store


@pytest.fixture(autouse=True)
def _isolate_mongo(monkeypatch):
    for key in [k for k in os.environ if k.startswith("MONGODB_")]:
        monkeypatch.delenv(key)

    monkeypatch.setattr(mongo_module, "_client", None)

    monkeypatch.setattr(experiment_logger, "uri", "")
    monkeypatch.setattr(experiment_logger, "mas_name", "")
    monkeypatch.setattr(experiment_logger, "mas_key", "")
    monkeypatch.setattr(experiment_logger, "_client", None)
    monkeypatch.setattr(experiment_logger, "_collection", None)

    monkeypatch.setattr(submission_store, "uri", "")
    monkeypatch.setattr(submission_store, "mas_name", "")
    monkeypatch.setattr(submission_store, "mas_key", "")
    monkeypatch.setattr(submission_store, "host", "")
    monkeypatch.setattr(submission_store, "_client", None)
    monkeypatch.setattr(submission_store, "_collection", None)
