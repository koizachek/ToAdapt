# ToAdapt

// ToAdapt — Multi-Agent Scaffolding System für BWL A
// Universität St. Gallen · ~2.000 Studierende · 80 Übungsgruppen

// === USER LAYER ===

Student Group [shape: oval, icon: users, color: teal] {
  6er-Team
  Simultaner Zugriff
  Chat UI (DE/EN)
}

// === FRONTEND ===

Frontend [shape: rectangle, icon: monitor, color: blue] {
  React/Next.js
}

Chat Window [shape: rectangle, color: blue]
TP Progress [shape: rectangle, color: blue]
Case Reference Panel [shape: rectangle, color: blue]
Presence Bar [shape: rectangle, color: blue]
Language Switch [shape: rectangle, color: blue]

Frontend > Chat Window
Frontend > TP Progress
Frontend > Case Reference Panel
Frontend > Presence Bar
Frontend > Language Switch

// === REALTIME LAYER ===

WebSocket Manager [shape: diamond, icon: zap, color: purple] {
  Gruppenchat
  Broadcast
  Presence
}

Student Group > WebSocket Manager: WS connect
WebSocket Manager > Frontend: Real-time updates

// === ORCHESTRATOR ===

Session Orchestrator [shape: hexagon, icon: cpu, color: purple] {
  Phase-Erkennung
  Agent-Routing
  Metacognitive-First-Sequenzierung
  Intent-Klassifikation
}

WebSocket Manager > Session Orchestrator: User messages

// === GROUP MEMORY ===

Group Memory [shape: cylinder, icon: database, color: gray] {
  TP1: Herausforderungen, Stakeholder
  TP2: Strategie, Trade-offs, KPI
  TP3: Decision Log (4 Felder)
  TP4: Integration, Risiken
  Konversationshistorie
  Scaffolding-Intensität
}

Session Orchestrator <> Group Memory: Read/Write state

// === SCAFFOLDING AGENTS ===

Metacognitive Agent [shape: rectangle, icon: brain, color: coral] {
  Reflexion
  Planung
  Monitoring
  FIRST in sequence
}

Strategic Agent [shape: rectangle, icon: compass, color: coral] {
  Herangehensweise
  Priorisierung
  Trade-off-Denken
  Implizite Frameworks
}

Conceptual Agent [shape: rectangle, icon: book-open, color: coral] {
  Domänenwissen
  Case-Verständnis
  TP-weise Freischaltung
  Exhibit-Referenzen
}

Procedural Agent [shape: rectangle, icon: layout, color: coral] {
  Abgabeformat
  Strukturhilfe
  TP-spezifisch
  Anti-Formatrezept
}

Session Orchestrator > Metacognitive Agent: 1. Aktiviert zuerst
Session Orchestrator > Strategic Agent: 2. Nach Reflexion
Session Orchestrator > Conceptual Agent: 3. Bei Inhaltsfragen
Session Orchestrator > Procedural Agent: 4. Bei Formatfragen

// === GUARDRAIL LAYER ===

Guardrail Layer [shape: rectangle, icon: shield, color: amber] {
  Answer Filter
  Framework Name Filter
  Phase Consistency Filter
  Anti-Musterlösung
}

Metacognitive Agent > Guardrail Layer: Response
Strategic Agent > Guardrail Layer: Response
Conceptual Agent > Guardrail Layer: Response
Procedural Agent > Guardrail Layer: Response

Guardrail Layer > WebSocket Manager: Validated response

// === TP CONFIGURATION ===

TP1 Config [shape: rectangle, color: green] {
  Bloom 2–4
  Slides
  SGMM, Stakeholder
  Case Kap. A
}

TP2 Config [shape: rectangle, color: green] {
  Bloom 4–5
  Memo
  +Porter/RBV (implizit)
  Case Kap. A+B
}

TP3 Config [shape: rectangle, color: green] {
  Bloom 3–5
  Decision Log
  +4P, TK, Elastizität
  Case Kap. A+B+C
}

TP4 Config [shape: rectangle, color: green] {
  Bloom 5–6
  Strategy-on-a-Page
  +GM-Canvas, SGMM-Dim.
  Case Kap. A+B+C+D
}

TP1 Config > Session Orchestrator: Active config
TP2 Config > Session Orchestrator: Active config
TP3 Config > Session Orchestrator: Active config
TP4 Config > Session Orchestrator: Active config

// === RAG / KNOWLEDGE ===

RAG Knowledge Layer [shape: cylinder, icon: search, color: green] {
  Vektor-DB (ChromaDB)
  TP-weise Access Control
}

ON Case v3 [shape: document, color: green] {
  4 Kapitel
  17 Exhibits
}

TP Briefings [shape: document, color: green] {
  Aufgabenstellungen
  Bewertungskriterien
}

Rubrics [shape: document, color: green] {
  Pfadoffene Rubrics
  "So ja" Beispiele
}

BWL Frameworks [shape: document, color: green] {
  Denkprinzipien
  OHNE Modellnamen
}

ON Case v3 > RAG Knowledge Layer
TP Briefings > RAG Knowledge Layer
Rubrics > RAG Knowledge Layer
BWL Frameworks > RAG Knowledge Layer

RAG Knowledge Layer > Conceptual Agent: Retrieval
RAG Knowledge Layer > Strategic Agent: Retrieval

// === GLOBAL SCHEDULE ===

Global TP Schedule [shape: rectangle, icon: calendar, color: gray] {
  Deadlines für alle Gruppen gleich
  Automatischer TP-Wechsel
}

Global TP Schedule > Session Orchestrator: Current phase

// === DASHBOARD (DOZIERENDE) ===

Dozierenden Dashboard [shape: rectangle, icon: bar-chart, color: blue] {
  Aggregierte Insights
  Topic Heatmap
  Stuck Groups
  Activity Chart
  KEINE Chat-Logs
}

Group Memory > Dozierenden Dashboard: Aggregierte Daten

// === RESEARCH LOGGING ===

Research Logger [shape: cylinder, icon: archive, color: gray] {
  Vollständige Konversationen
  Agent-Routing-Decisions
  Guardrail-Triggers
  Session-Metriken
  NUR für Forschende
}

Session Orchestrator > Research Logger: All events
Guardrail Layer > Research Logger: Filter events
WebSocket Manager > Research Logger: Activity data

// === BLOCKED ===

NORDIC HOME [shape: rectangle, icon: x-circle, color: red] {
  GESPERRT
  Klausur-Case
  Nicht im RAG
}