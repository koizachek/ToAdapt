"""Lokalen Import von Prolific-Exporten in die Repo-Datenstruktur."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST_ROOT = REPO_ROOT / "data" / "prolific_runs"
IGNORED_FILE_NAMES = {".DS_Store"}


@dataclass(frozen=True)
class ImportedFile:
    source_path: str
    relative_path: str
    size_bytes: int
    sha256: str


def _slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip().lower()).strip("-")
    return slug or "prolific-run"


def _default_batch_name(source: Path) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{_slugify(source.stem)}"


def _iter_files(source: Path) -> list[Path]:
    if source.is_file():
        return [source]

    files: list[Path] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        if path.name in IGNORED_FILE_NAMES:
            continue
        if any(part.startswith(".") for part in path.relative_to(source).parts):
            continue
        files.append(path)
    return files


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def import_prolific_runs(
    *,
    source: Path,
    batch_name: str | None = None,
    dest_root: Path = DEFAULT_DEST_ROOT,
) -> dict[str, object]:
    source = source.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Quelle nicht gefunden: {source}")

    files = _iter_files(source)
    if not files:
        raise ValueError(f"Keine importierbaren Dateien gefunden unter: {source}")

    batch = batch_name or _default_batch_name(source)
    raw_dir = dest_root / "raw" / batch
    manifest_dir = dest_root / "manifests"
    manifest_path = manifest_dir / f"{batch}.json"

    if raw_dir.exists():
        raise FileExistsError(f"Zielbatch existiert bereits: {raw_dir}")
    if manifest_path.exists():
        raise FileExistsError(f"Manifest existiert bereits: {manifest_path}")

    imported_files: list[ImportedFile] = []
    for file_path in files:
        relative_path = file_path.name if source.is_file() else str(file_path.relative_to(source))
        target_path = raw_dir / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, target_path)

        imported_files.append(
            ImportedFile(
                source_path=str(file_path),
                relative_path=relative_path,
                size_bytes=target_path.stat().st_size,
                sha256=_sha256(target_path),
            )
        )

    manifest_dir.mkdir(parents=True, exist_ok=True)
    imported_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "batch_name": batch,
        "imported_at": imported_at,
        "source": str(source),
        "raw_dir": str(raw_dir),
        "file_count": len(imported_files),
        "total_bytes": sum(item.size_bytes for item in imported_files),
        "files": [
            {
                "source_path": item.source_path,
                "relative_path": item.relative_path,
                "size_bytes": item.size_bytes,
                "sha256": item.sha256,
            }
            for item in imported_files
        ],
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Datei oder Verzeichnis mit Prolific-Exporten")
    parser.add_argument(
        "--batch",
        dest="batch_name",
        help="Optionaler Batch-Name fuer den Zielordner unter data/prolific_runs/raw/",
    )
    parser.add_argument(
        "--dest-root",
        default=str(DEFAULT_DEST_ROOT),
        help="Zielwurzel fuer den Import (Default: data/prolific_runs)",
    )
    args = parser.parse_args()

    manifest = import_prolific_runs(
        source=Path(args.source),
        batch_name=args.batch_name,
        dest_root=Path(args.dest_root).expanduser().resolve(),
    )
    print(
        f"Importiert: {manifest['file_count']} Dateien nach {manifest['raw_dir']} "
        f"(Manifest: {Path(manifest['raw_dir']).parents[1] / 'manifests' / (manifest['batch_name'] + '.json')})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
