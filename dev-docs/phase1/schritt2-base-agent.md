# Phase 1 / Schritt 2 — Base Agent & LLM-Anbindung

**Datum:** 2026-04-08  
**Status:** abgeschlossen

---

## Ziel

Abstrakte Basisklasse für alle Scaffolding-Agenten mit Anthropic-LLM-Anbindung,
plus erstem konkreten Agenten (MetacognitiveAgent) und zugehörigen System-Prompt-Vorlagen.

---

## Entscheidungen

### LLM-Anbindung
- **Anthropic SDK** (`AsyncAnthropic`) als primärer Provider — `claude-sonnet-4-6` per Default
- Provider-Wahl via `LLM_PROVIDER`-Env-Variable (OpenAI-Support in Phase 2)
- `llm_client`-Parameter in `BaseAgent.__init__()` ist **injectable** → ermöglicht Mocking in Tests ohne echte API-Calls

### Prompt-Management
- System-Prompts als Markdown-Dateien in `/backend/config/agent_prompts/`
- Namensschema: `{agent_type}_tp{n}.md` (z.B. `metacognitive_tp1.md`)
- Jede Vorlage enthält Platzhalter `{group_memory}` und `{conversation_history}`
- Fallback-Prompt wenn Datei fehlt (verhindert harte Fehler, loggt Warning)

### Nachrichten-Format
- `_format_history()` konvertiert `list[Message]` → Anthropic-Messages-Format
- `_deduplicate_roles()` stellt alternierende Rollen sicher (Anthropic-Requirement)
- Aufeinanderfolgende User-Nachrichten werden durch `\n\n` zusammengeführt

### Verbotene Inhalte in Prompts
- Test prüft automatisch: keine verbotenen Framework-Namen in Prompt-Vorlagen
- Verbote gelten auch für die "Was du nicht tust"-Liste in den Prompts
- Dort: allgemeine Formulierungen statt spezifischer Modellnamen

### Settings
- `backend/config/settings.py` mit `pydantic-settings` und `model_config` (Pydantic v2)
- Singleton via `@lru_cache` — `settings` global importierbar
- `llm_max_tokens = 1024` als konfigurierbarer Default

---

## Erstellte Dateien

| Datei | Zweck |
|---|---|
| `backend/config/settings.py` | Pydantic-Settings für alle Env-Vars |
| `backend/config/agent_prompts/metacognitive_tp1.md` | Metacognitiver Agent, TP1 |
| `backend/config/agent_prompts/metacognitive_tp2.md` | Metacognitiver Agent, TP2 |
| `backend/config/agent_prompts/metacognitive_tp3.md` | Metacognitiver Agent, TP3 |
| `backend/config/agent_prompts/metacognitive_tp4.md` | Metacognitiver Agent, TP4 |
| `backend/agents/base_agent.py` | `BaseAgent` (ABC), `AgentResponse`, Hilfsfunktionen |
| `backend/agents/metacognitive.py` | `MetacognitiveAgent` (erste Subklasse) |
| `backend/agents/__init__.py` | Öffentliche Exports |

---

## Tests

```
tests/test_base_agent.py — 22 Tests für Schritt 2

test_agent_response_is_valid_model           AgentResponse ist gültiges Pydantic-Modell
test_agent_response_with_guardrails          guardrails_triggered korrekt übertragen
test_metacognitive_prompt_template_exists_for_all_tps  Alle 4 Vorlagen vorhanden
test_metacognitive_prompt_contains_no_forbidden_frameworks  Kein Framework-Name in Prompts
test_metacognitive_prompt_references_tp_context  Jeder Prompt hat TP-Kontext
test_metacognitive_agent_type                agent_type == "metacognitive"
test_metacognitive_builds_system_prompt_tp1  System-Prompt nicht leer
test_metacognitive_format_group_memory_empty  Fallback-Text korrekt
test_metacognitive_format_group_memory_with_data  TP1/TP2-Daten korrekt serialisiert
test_deduplicate_roles_*                     3 Tests für Role-Deduplication
```

---

## Offene TODOs für Phase 2

- [ ] OpenAI-Provider als Alternative (via `llm_provider`-Setting)
- [ ] Streaming-Support (`stream=True`) für bessere UX
- [ ] `_format_history()`: Konversationslänge begrenzen (Token-Budget)
- [ ] Strategic, Conceptual, Procedural Agenten + zugehörige Prompt-Vorlagen
- [ ] Prompt-Vorlagen für alle 4 Agenten × 4 TPs = 16 Dateien total
