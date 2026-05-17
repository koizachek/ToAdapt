from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "import_prolific_runs.py"
SPEC = importlib.util.spec_from_file_location("import_prolific_runs", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_import_prolific_runs_copies_files_and_writes_manifest(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "participants.csv").write_text("participant_id,status\np1,APPROVED\n", encoding="utf-8")
    nested = source / "details"
    nested.mkdir()
    (nested / "session.json").write_text('{"session_id":"s1"}\n', encoding="utf-8")
    (source / ".DS_Store").write_text("ignored", encoding="utf-8")

    dest_root = tmp_path / "repo_data"
    manifest = MODULE.import_prolific_runs(
        source=source,
        batch_name="pilot-batch",
        dest_root=dest_root,
    )

    raw_dir = dest_root / "raw" / "pilot-batch"
    assert manifest["batch_name"] == "pilot-batch"
    assert manifest["file_count"] == 2
    assert (raw_dir / "participants.csv").read_text(encoding="utf-8").startswith("participant_id")
    assert (raw_dir / "details" / "session.json").exists()

    manifest_path = dest_root / "manifests" / "pilot-batch.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["file_count"] == 2
    assert {item["relative_path"] for item in payload["files"]} == {
        "participants.csv",
        "details/session.json",
    }
