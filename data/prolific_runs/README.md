# Prolific Runs

Lokaler Ablageort fuer Rohdaten und abgeleitete Dateien aus Prolific-Runs.

Konvention:

- `raw/<batch-name>/`: unveraenderte Exporte aus Prolific oder angrenzenden Tools
- `manifests/<batch-name>.json`: Import-Metadaten mit Dateiliste, Groessen und SHA-256
- `derived/`: bereinigte oder angereicherte Folgeartefakte fuer Analysen

Die Inhalte unter `data/prolific_runs/` sind bewusst per Root-`.gitignore` aus Git ausgeschlossen.

Beispielimport:

```bash
python scripts/import_prolific_runs.py ~/Downloads/prolific-export --batch may-2026-pilot
```
