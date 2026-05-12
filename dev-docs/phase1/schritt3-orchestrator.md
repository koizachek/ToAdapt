# Phase 1 / Schritt 3 — Einfacher Orchestrator

**Datum:** 2026-04-08  
**Status:** abgeschlossen

---

## Ziel

Minimaler `SessionOrchestrator`, der Gruppen-Nachrichten empfängt und an den
metacognitiven Agenten weiterleitet. Noch kein Intent-basiertes Routing —
das kommt in Phase 2 mit den anderen drei Agenten.

---

## Entscheidungen

### Single-Agent-Betrieb (Phase 1)
- `routing.select_agent()` gibt immer `MetacognitiveAgent` zurück
- Alle TP-Phasen verwenden denselben Agenten (aber unterschiedliche System-Prompts)
- Vorbereitet für Phase 2: `message`-Parameter in `select_agent()` wird später
  für Intent-Klassifikation genutzt

### Metacognitive-First-Sequenzierung
- `sequencing.py`: Heuristik — nach ≥ 2 Nachrichten gilt Phase als "abgeschlossen"
- Flag `session.metacognitive_phase_complete` kann explizit gesetzt werden
- In Phase 3 ersetzt durch Inhaltsanalyse der Agent-Outputs

### Session-Verwaltung (In-Memory, Phase 1)
- `SessionOrchestrator` erstellt bei Bedarf eine neue `Session` (in-memory)
- `message_count` und `last_activity` werden pro Route-Call aktualisiert
- Persistenz in PostgreSQL kommt in Phase 2

### WebSocket-Integration
- `main.py` erstellt `SessionOrchestrator` beim WebSocket-Verbindungsaufbau
- Konversationshistorie (`list[Message]`) wird lokal im WebSocket-Handler akkumuliert
- `broadcast_agent_response()` wird jetzt tatsächlich aufgerufen (war vorher TODO)

---

## Erstellte Dateien

| Datei | Zweck |
|---|---|
| `backend/orchestrator/session.py` | `SessionOrchestrator` — zentrale Steuerung |
| `backend/orchestrator/routing.py` | Agent-Selektion (Phase 1: immer metacognitiv) |
| `backend/orchestrator/sequencing.py` | Metacognitive-First-Logik |
| `backend/orchestrator/__init__.py` | Export von `SessionOrchestrator` |
| `backend/main.py` | Orchestrator in WebSocket-Handler eingebunden |

---

## Tests

```
tests/test_base_agent.py — 5 zusätzliche Tests für Schritt 3

test_select_agent_returns_metacognitive_phase1     Routing → metacognitiv
test_select_agent_returns_metacognitive_all_tps    Für alle 4 TPs metacognitiv
test_orchestrator_routes_and_returns_response      Gemockter LLM-Call, Response korrekt
test_orchestrator_increments_message_count         message_count +1 pro Route-Call
test_orchestrator_metacognitive_phase_initially_incomplete  Startet bei 0
test_orchestrator_metacognitive_phase_complete_after_messages  Heuristik greift
```

---

## Gesamtstatus nach Schritt 3

```
27/27 Tests passing (test_base_agent.py + test_skeleton.py)
```

---

## Offene TODOs für Phase 2

- [ ] Intent-Klassifikation (LLM-basiert oder Pattern-Matching)
- [ ] Strategic, Conceptual, Procedural Agenten einbinden
- [ ] Guardrail-Layer nach `agent.respond()` schalten
- [ ] `SessionOrchestrator` mit PostgreSQL-Session persistieren
- [ ] Redis: Session-Cache für schnelle Wiederherstellung nach Reconnect
- [ ] `metacognitive_phase_complete`: Inhaltsbasierte Erkennung statt Heuristik
