# ToAdapt

A multi-agent scaffolding system for collaborative problem-solving in higher education. Groups of students work through ill-structured business cases across multiple phases, supported by AI agents that scaffold their thinking — without giving answers.

Built on empirically validated findings from an orchestrating scaffolding AI agents (metacognitive-first sequencing, Cohen's d = 0.44).

## Architecture

```
Frontend (React/Next.js)
  ↕ WebSocket (group chat, presence)
Session Orchestrator
  ├── Metacognitive Agent    (1st — reflection, planning)
  ├── Strategic Agent        (2nd — approach, trade-offs)
  ├── Conceptual Agent       (3rd — domain knowledge)
  └── Procedural Agent       (4th — format, structure)
  ↕
Guardrail Layer              (no direct answers, implicit framework steering)
  ↕
RAG Knowledge Layer          (phase-gated case materials, rubrics, frameworks)
  ↕
Group Memory (PostgreSQL)    (persistent state across phases)
Research Logger              (comprehensive interaction logging)
Instructor Dashboard         (aggregated insights, no chat logs)
```

## Key Design Principles

- **Scaffolding, not answering** — agents ask questions and give thinking prompts, never solutions
- **Metacognitive-first** — every session starts with reflection before content-focused support
- **Phase-aware** — agent configuration, available knowledge, and allowed frameworks adapt per phase
- **Group-native** — all members interact simultaneously; persistent group memory across phases
- **Guardrailed** — filters enforce no direct answers, no framework name-dropping, phase consistency

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React, Next.js, Tailwind, next-intl (DE/EN) |
| Realtime | WebSocket (group chat + presence) |
| Backend | Python 3.11+, FastAPI, Pydantic v2 |
| LLM | OpenAI / Anthropic API |
| RAG | ChromaDB (vector search, phase-gated access control) |
| Database | PostgreSQL (groups, sessions, memory), Redis (session cache) |
| Logging | structlog, JSON/CSV export for research data |
| Deployment | Docker, docker-compose |

## Setup

```bash
git clone https://github.com/koizachek/ToAdapt.git
cd ToAdapt
cp .env.example .env  # add API keys
docker-compose up
```

## License

MIT