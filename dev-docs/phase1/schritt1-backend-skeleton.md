# Phase 1 / Schritt 1 — Backend-Skeleton

**Datum:** 2026-04-07  
**Status:** abgeschlossen

---

## Ziel

Lauffähiges FastAPI-Backend mit Datenmodellen und WebSocket-Grundstruktur als Basis für alle weiteren Phasen. Kein Business-Logik-Code, nur das Fundament.

---

## Entscheidungen

### Framework-Wahl
- **FastAPI** (nicht Django/Flask): native async/await-Unterstützung, automatische OpenAPI-Docs, WebSocket-Support out-of-the-box, Pydantic v2 integriert.
- **Pydantic v2** für alle Datenmodelle: Validierung, Serialisierung, Type Safety ohne Overhead.
- **structlog** statt Standard-logging: strukturierte JSON-Logs, leichter für Forschungs-Auswertung parsebar.

### WebSocket-Design
- Ein WebSocket-Endpunkt pro Gruppenmitglied: `/ws/{group_id}/{user_id}`
- `ConnectionManager` verwaltet Rooms als `dict[group_id → dict[user_id → WebSocket]]`
- Alle Broadcasts gehen über den `ConnectionManager` — keine direkten WebSocket-Calls aus Business-Logik
- Typing-Indikator (`agent_typing`) als separates Event, damit das Frontend sofort reagieren kann

### Session-Modell
- Sessions sind flüchtig (kein DB-Persist in Phase 1); werden in Phase 2 mit PostgreSQL verankert
- `current_tp_phase()` bestimmt die aktive Phase anhand globaler Deadlines aus `TP_SCHEDULE` — kein manueller Eingriff pro Gruppe nötig

### Ordnerstruktur
- Alle Module unter `backend/` als Python-Package (mit `__init__.py`)
- `config/tp_configs.py` enthält TP_CONFIGS + TP_SCHEDULE als Single Source of Truth
- Stubs (`__init__.py`) für noch nicht implementierte Module (orchestrator, agents, memory, guardrails, rag): verhindert ImportErrors in späteren Integrationstests

---

## Erstellte Dateien

| Datei | Zweck |
|---|---|
| `backend/main.py` | FastAPI-App, Lifespan, CORS, Routen, WebSocket-Endpunkt |
| `backend/models/group.py` | `Group`, `GroupMember`, `GroupMemoryState`, `TPPhase` |
| `backend/models/message.py` | `Message` (user/agent/system, mit agent_type) |
| `backend/models/session.py` | `Session`, `SessionCreate`, `SessionResponse` |
| `backend/realtime/websocket.py` | `ConnectionManager` (connect/disconnect/broadcast) |
| `backend/realtime/presence.py` | Presence-Update-Logic |
| `backend/realtime/broadcast.py` | Typisierte Broadcast-Funktionen |
| `backend/config/tp_configs.py` | `TP_CONFIGS` (1–4), `TP_SCHEDULE`, `current_tp_phase()` |
| `tests/test_skeleton.py` | 5 Smoke-Tests |
| `requirements.txt` | Python-Dependencies |
| `pyproject.toml` | Build-Config, pytest-Config, ruff/mypy-Config |
| `.env.example` | API-Keys-Template |
| `Dockerfile` | Single-Stage Python 3.11 Image |
| `docker-compose.yml` | api + db (Postgres) + redis + chromadb |

---

## API-Endpunkte

| Method | Path | Beschreibung |
|---|---|---|
| `GET` | `/health` | Statuscheck + aktuelle TP-Phase |
| `POST` | `/sessions` | Session erstellen, WebSocket-URL zurückgeben |
| `WS` | `/ws/{group_id}/{user_id}` | Gruppen-Chat WebSocket |

---

## WebSocket-Protokoll (JSON)

**Client → Server:**
```json
{ "type": "message", "content": "Wie sollen wir vorgehen?" }
```

**Server → alle Clients (Broadcast):**
```json
// Andere Gruppenmitglieder sehen die Nachricht:
{ "event": "user_message", "user_id": "u1", "display_name": "Lisa", "content": "...", "timestamp": "..." }

// Agent antwortet:
{ "event": "agent_response", "agent_type": "metacognitive", "content": "...", "timestamp": "..." }

// Tipp-Indikator:
{ "event": "agent_typing", "agent_type": "metacognitive", "is_typing": true }

// Presence:
{ "event": "presence_update", "online": ["Lisa", "Max", "Kai"], "count": 3 }
```

---

## Tests

```
tests/test_skeleton.py — 5/5 passed

test_health                          GET /health → 200, status ok
test_create_session                  POST /sessions → 201, korrekte WebSocket-URL
test_current_tp_phase_within_window  Datumslogik innerhalb aktiver Phasen
test_current_tp_phase_before_course  Vor Kursbeginn → TP1
test_current_tp_phase_after_course   Nach Kursende → TP4
```

---

## Offene TODOs für Phase 2

- [ ] `POST /sessions`: DB-Persistenz (PostgreSQL via asyncpg)
- [ ] Auth: Gruppencode-Validierung + JWT
- [ ] Orchestrator-Aufruf in `main.py` (Stub vorhanden, markiert mit `TODO Phase 2`)
- [ ] `GroupMemory` in PostgreSQL persistieren
- [ ] Redis: Session-Cache, Rate Limiting
- [ ] WebSocket: Reconnect-Logik (exponential backoff im Frontend)
