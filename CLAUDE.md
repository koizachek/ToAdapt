# ToAdapt — Multi-Agent Scaffolding System für BWL A

## Projektübersicht

**ToAdapt** ist ein agentic AI-System, das Studierende der Universität St.Gallen (~2.000, in 6er-Gruppen, 80 Übungsgruppen) bei der Bearbeitung von Business Cases **zwischen** den vier Touchpoints (TP1–TP4) des reformierten BWL-A-Kurses unterstützt.

**GitHub-Repo:** https://github.com/koizachek/ToAdapt  
**Tech-Stack:** Python (FastAPI Backend), React/Next.js Frontend, LLM-API (OpenAI/Anthropic), Vektor-DB (ChromaDB/Pinecone) für RAG  
**Lerndesign-Grundlage:** BWL-A-Lehrdesign-Reform (Constructive Alignment nach Biggs, 2003), validiert durch CompEd-Publikation zu Multi-Agent Scaffolding (Hao et al., 2026)

---

## Lehrdesign-Kontext (MUST READ)

Das System ist in ein konkretes Lehrdesign eingebettet, das **nicht verletzt werden darf**. Die folgenden Prinzipien sind harte Constraints:

### Constructive Alignment
- 4 Touchpoints trainieren exakt die Kompetenzen, die in der Klausur geprüft werden
- TP1 (Verstehen, Bloom 2–4) → TP2 (Entscheiden, Bloom 4–5) → TP3 (Umsetzen, Bloom 3–5) → TP4 (Integrieren, Bloom 5–6)
- Klausur verwendet einen separaten Case (NORDIC HOME) — das System kennt NORDIC HOME **nicht** und darf ihn **nicht** verwenden

### Anti-Pattern-Design
- **Keine Musterlösungen** — Rubrics sind pfadoffen; jede schlüssig begründete Entscheidung kann volle Punkte erreichen
- **Implizite Framework-Steuerung** — das System darf **keine Modellnamen** nennen (kein "benutzt Porter's Five Forces"), sondern muss die Logik hinter den Modellen durch Fragen hervorrufen
- **Vier verschiedene Abgabeformate** — Slides (TP1) → Memo (TP2) → Decision Log (TP3) → Strategy-on-a-Page (TP4); das System muss formatspezifisch unterstützen, ohne Formatrezepte zu liefern

### Scaffolding, nicht Answer-Giving
Das System ist ein **Scaffolding-System**, kein Chatbot:
- Es gibt **niemals** direkte Antworten, Lösungsvorschläge oder fertige Textbausteine
- Es stellt **sokratische Fragen**, gibt **Denkimpulse**, verweist auf **relevante Case-Stellen**
- Es respektiert die **Zone of Proximal Development** der Gruppe

### Metacognitive-First-Prinzip
Empirisch validiert (CompEd-Paper: Cohen's d = 0.44): Jede Interaktionssession beginnt mit dem metacognitiven Agenten (Reflexion, Planung, Monitoring), bevor content-focused Agenten aktiviert werden.

---

## Systemarchitektur

### Gesamtaufbau

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                      │
│  Chat-UI · Gruppenansicht · TP-Fortschritt · Case-Ref   │
└─────────────────────┬───────────────────────────────────┘
                      │ WebSocket / REST
┌─────────────────────▼───────────────────────────────────┐
│               Session Orchestrator                       │
│  Phase-Erkennung · Agent-Routing · Gruppengedächtnis     │
│  Metacognitive-First-Sequenzierung                       │
├──────────┬──────────┬──────────┬────────────────────────┤
│  Meta-   │ Strate-  │ Konzep-  │   Prozeduraler         │
│ kognitiv │  gisch   │  tuell   │     Agent              │
├──────────┴──────────┴──────────┴────────────────────────┤
│               Guardrail Layer                            │
│  Anti-Answer · Implizite Frameworks · Pfadoffenheit      │
├─────────────────────────────────────────────────────────┤
│               RAG / Wissensschicht                       │
│  ON Case v3 · TP-Briefings · Rubrics · BWL-Frameworks   │
└─────────────────────────────────────────────────────────┘
```

### Kernkomponenten

#### 1. Session Orchestrator (`/backend/orchestrator/`)
Zentrale Steuerungslogik. Empfängt alle Gruppeninteraktionen und entscheidet:
- **Welcher Agent** aktiviert wird (basierend auf Konversationsverlauf + TP-Phase)
- **In welcher Reihenfolge** (metacognitive-first, dann strategic → conceptual → procedural)
- **Mit welcher Intensität** (high/medium/low basierend auf Gruppenfortschritt)

```python
# Pseudocode für Orchestrator-Logik
class SessionOrchestrator:
    def __init__(self, group_id: str, tp_phase: int):
        self.group_memory = GroupMemory(group_id)
        self.tp_config = TP_CONFIGS[tp_phase]  # Lädt TP-spezifische Constraints
        self.agent_sequence = ["metacognitive", "strategic", "conceptual", "procedural"]
        self.current_agent_idx = 0
    
    def route_message(self, message: str) -> AgentResponse:
        # 1. Klassifiziere die Anfrage
        intent = self.classify_intent(message)
        
        # 2. Prüfe, ob metacognitive Phase abgeschlossen
        if not self.metacognitive_phase_complete():
            return self.agents["metacognitive"].respond(message, self.get_context())
        
        # 3. Route zum passenden Agenten basierend auf Intent + TP-Phase
        agent = self.select_agent(intent)
        context = self.build_context(agent, message)
        
        # 4. Guardrail-Check auf Agent-Output
        response = agent.respond(message, context)
        return self.guardrails.validate(response)
```

#### 2. Scaffolding-Agenten (`/backend/agents/`)

Jeder Agent hat einen eigenen System-Prompt, der TP-abhängig konfiguriert wird.

**Metacognitiver Agent** — Reflexion, Planung, Selbstregulation
- Fragt: "Was ist euer Plan für diesen Touchpoint?"
- Fragt: "Wo seht ihr die größte Unsicherheit in eurer bisherigen Analyse?"
- Hilft bei der Selbsteinschätzung des Gruppenfortschritts
- Verweist auf vorige TP-Ergebnisse: "In TP1 habt ihr X als Herausforderung identifiziert — passt eure TP2-Strategie dazu?"

**Strategischer Agent** — Herangehensweise an die Aufgabe
- Hilft bei der Priorisierung: "Ihr habt drei Herausforderungen benannt — wie entscheidet ihr, welche zwei die kritischsten sind?"
- Gibt Denkhilfen zu Trade-offs: "Was gewinnt ON, wenn sie diesen Weg gehen? Was verlieren sie?"
- **NIEMALS:** "Benutzt die Transaktionskostentheorie" → **STATTDESSEN:** "Welche Faktoren — etwa wie spezialisiert die Leistung ist, wie oft sie benötigt wird — sprechen für oder gegen eine interne Lösung?"

**Konzeptueller Agent** — Domänenwissen und Case-Verständnis
- Verweist auf relevante Case-Stellen: "Schaut euch Exhibit 7 an — was sagt das über ONs Margenstruktur?"
- Stellt Verständnisfragen: "Ihr sprecht von Skalierung — was genau heißt das für ONs Wertschöpfungskette?"
- TP-spezifischer Wissenszugang (s.u.)

**Prozeduraler Agent** — Format und Struktur der Abgabe
- TP1: "Eure Slide hat 8 Bullet Points — wie könntet ihr verdichten?"
- TP2: "Ein Memo braucht eine durchgängige Argumentationslinie — lest euren Text laut vor: folgt die Logik?"
- TP3: "Euer Decision Log muss einen expliziten Rückbezug auf TP2 haben — wo ist der?"
- TP4: "Strategy-on-a-Page heißt radikale Verdichtung — was lässt ihr weg, und warum?"

#### 3. Gruppengedächtnis (`/backend/memory/`)

Persistenter Zustand pro Gruppe über das gesamte Semester:

```python
class GroupMemory:
    group_id: str
    members: list[str]
    
    # TP-Ergebnisse (vom ÜGL oder System extrahiert)
    tp1_challenges: list[str]       # Identifizierte Herausforderungen
    tp1_stakeholders: list[str]     # Stakeholder-Mapping
    tp2_strategy: str               # Strategische Empfehlung
    tp2_tradeoffs: list[str]        # Explizite Trade-offs
    tp2_kpi: str                    # Gewählte Kennzahl
    tp3_decisions: dict             # Decision Log Felder 1–4
    tp3_consistency_assessment: str  # Konsistenz-Selbsteinschätzung
    
    # Interaktionsverlauf
    conversation_history: list[Message]
    scaffolding_intensity: str      # "high" | "medium" | "low"
    metacognitive_readiness: float  # 0.0–1.0
```

#### 4. TP-Konfigurationen (`/backend/config/`)

Jeder Touchpoint hat eine eigene Konfiguration, die die Agenten steuert:

```python
TP_CONFIGS = {
    1: {
        "name": "Analyse & Stakeholder",
        "bloom_levels": [2, 3, 4],
        "format": "3 Slides (PDF)",
        "allowed_frameworks": [
            "SGMM (Umwelt-Organisation-Spannungsfeld)",
            "Stakeholder-Mapping (Einfluss/Betroffenheit)"
        ],
        "forbidden_framework_names": [
            "Porter", "RBV", "Five Forces", "VRIO",
            "Transaktionskosten", "Preiselastizität"
        ],
        "case_chapters": ["A"],  # Nur Kapitel A des ON-Case
        "key_questions": [
            "Welche Herausforderungen sind am kritischsten?",
            "Wo liegt das Spannungsfeld Umwelt ↔ Organisation?",
            "Welcher Stakeholder hat den höchsten Einfluss?"
        ],
        "rubric_reference": "tp1_rubric.json",
        "max_slides": 3,
        "max_bullets_per_slide": 6,
        "individual_component": {
            "question": "Was würden Sie an Ihrer eigenen Analyse konkret verändern – und warum?",
            "points": 6,
            "time_minutes": 5
        }
    },
    2: {
        "name": "Strategische Entscheidung",
        "bloom_levels": [4, 5],
        "format": "Management-Memo (1 Seite, PDF)",
        "allowed_frameworks": [
            "SGMM", "Stakeholder-Mapping",
            "Wettbewerbslogik (Kosten vs. Differenzierung)",
            "Ressourcenbasierte Logik (VRIO-Prinzip, ohne Namen)",
            "KPI und Steuerungslogik"
        ],
        "forbidden_framework_names": [
            "Porter", "Five Forces", "RBV", "VRIO",
            "Transaktionskosten", "Preiselastizität", "4P", "Marketing-Mix"
        ],
        "case_chapters": ["A", "B"],
        "requires_tp1_reference": True,
        "key_questions": [
            "Wie soll ON wachsen?",
            "Worauf basiert der Wettbewerbsvorteil?",
            "Welcher Trade-off wird bewusst eingegangen?",
            "Welche Kennzahl misst den Erfolg?"
        ],
        "rubric_reference": "tp2_rubric.json",
        "individual_component": {
            "question": "Welche Entscheidung würden Sie anders treffen?",
            "points": 8,
            "time_minutes": 5
        }
    },
    3: {
        "name": "Strategie in den Markt übersetzen",
        "bloom_levels": [3, 4, 5],
        "format": "Decision Log (max. 2 Seiten A4, PDF)",
        "allowed_frameworks": [
            "Alle aus TP1+TP2",
            "Preiselastizität (implizit: 'Wie reagieren Kunden auf Preisänderungen?')",
            "Marketing-Mix (implizit: 'Kommunikation und Positionierung')",
            "Transaktionskostenlogik (implizit: 'Make-or-Buy-Faktoren')"
        ],
        "forbidden_framework_names": [
            "Preiselastizität", "4P", "Marketing-Mix",
            "Transaktionskostentheorie", "TCE"
        ],
        "case_chapters": ["A", "B", "C"],
        "requires_tp2_reference": True,  # Expliziter Strategiebezug!
        "decision_fields": [
            "Preisstrategie",
            "Kommunikation & Positionierung",
            "Make-or-Buy",
            "Digitalisierung & Prozesse"
        ],
        "key_questions": [
            "Wie hängt diese Preisentscheidung mit eurer TP2-Strategie zusammen?",
            "Worauf verzichtet ON mit dieser Preispositionierung bewusst?",
            "Welche Kundengruppen werden nicht angesprochen?",
            "Sind eure vier Entscheidungen untereinander konsistent?"
        ],
        "rubric_reference": "tp3_rubric.json",
        "individual_component": {
            "question": "Wo weicht die Umsetzung am stärksten von der Strategie ab?",
            "points": 8,
            "time_minutes": 5
        }
    },
    4: {
        "name": "Integration & Gesamtbild",
        "bloom_levels": [5, 6],
        "format": "Strategy-on-a-Page (1 Seite, visuell + Text)",
        "allowed_frameworks": [
            "Alle aus TP1–TP3",
            "Geschäftsmodell-Logik (Wertversprechen, Wertschöpfung, Erlös)",
            "SGMM-Gestaltungsdimensionen (Strategie, Struktur, Kultur, Prozesse)"
        ],
        "case_chapters": ["A", "B", "C", "D"],
        "requires_tp123_reference": True,
        "areas": [
            "Strategische Priorisierung (5 Pkt)",
            "Geschäftsmodell-Charakterisierung (5 Pkt)",
            "Gestaltungsdimensionen + Wechselwirkungen (4 Pkt)",
            "Risiken (optional, +3 Bonus)"
        ],
        "key_questions": [
            "Wie hängen TP1-Analyse, TP2-Strategie und TP3-Umsetzung zusammen?",
            "Welche Gestaltungsdimensionen verändern sich am stärksten?",
            "Was passiert, wenn eure riskanteste Entscheidung scheitert?",
            "Wo auf der Seite zeigt ihr Systemverständnis?"
        ],
        "rubric_reference": "tp4_rubric.json",
        "individual_component": {
            "question": "Riskanteste Entscheidung + Revisionskonsequenz (Kaskadeneffekt)",
            "points": 10,
            "time_minutes": 10
        }
    }
}
```

#### 5. Guardrail Layer (`/backend/guardrails/`)

Jede Agent-Antwort wird vor der Auslieferung geprüft:

```python
class GuardrailLayer:
    def validate(self, response: str, tp_config: dict) -> str:
        # 1. Antwort-Check: Gibt der Agent eine direkte Lösung?
        if self.contains_direct_answer(response):
            return self.rephrase_as_question(response)
        
        # 2. Framework-Name-Check
        for name in tp_config["forbidden_framework_names"]:
            if name.lower() in response.lower():
                response = self.remove_framework_name(response, name)
        
        # 3. Musterlösungs-Check: Klingt die Antwort wie ein Lösungsvorschlag?
        if self.solution_pattern_detected(response):
            return self.convert_to_scaffolding_question(response)
        
        # 4. Konsistenz-Check: Passt die Antwort zur TP-Phase?
        if not self.tp_phase_appropriate(response, tp_config):
            return self.adjust_to_phase(response, tp_config)
        
        return response
```

#### 6. RAG-Wissensschicht (`/backend/rag/`)

Chunking und Indexierung der Kursmaterialien:

- **ON Running Case v3** — Kapitel A–D, 17 Exhibits, TP-weise freigeschaltet
- **TP-Briefings** — Aufgabenstellungen, Bewertungskriterien (aber NICHT die Rubric-Details für Dozierende)
- **BWL-Frameworks** — Erklärungen der impliziten Frameworks, OHNE Modellnamen, formuliert als Denkprinzipien
- **Beispielantworten** — Nur die "So ja"-Beispiele aus den Rubrics, als Qualitätsanker (nicht als Musterlösungen!)

**WICHTIG:** NORDIC HOME ist **nicht** im RAG-Index. Der Klausur-Case ist geheim.

---

## Verzeichnisstruktur

```
ToAdapt/
├── CLAUDE.md                    # Diese Datei
├── README.md                    # Projekt-README
├── .env.example                 # API-Keys Template
│
├── backend/
│   ├── main.py                  # FastAPI Entrypoint
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── session.py           # SessionOrchestrator Klasse
│   │   ├── routing.py           # Agent-Routing-Logik
│   │   └── sequencing.py        # Metacognitive-first Sequenzierung
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py        # Basis-Klasse für alle Agenten
│   │   ├── metacognitive.py     # Reflexion, Planung, Monitoring
│   │   ├── strategic.py         # Herangehensweise, Priorisierung
│   │   ├── conceptual.py        # Domänenwissen, Case-Verständnis
│   │   └── procedural.py        # Format, Struktur, Abgabehilfe
│   │
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── group_memory.py      # Persistenter Gruppenzustand
│   │   └── session_state.py     # Sitzungszustand (flüchtig)
│   │
│   ├── guardrails/
│   │   ├── __init__.py
│   │   ├── answer_filter.py     # Keine direkten Antworten
│   │   ├── framework_filter.py  # Keine Modellnamen
│   │   └── phase_filter.py      # TP-Phasen-Konsistenz
│   │
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── indexer.py           # Dokument-Chunking + Indexierung
│   │   ├── retriever.py         # Kontext-Retrieval
│   │   └── tp_access_control.py # TP-weise Kapitel-Freischaltung
│   │
│   ├── config/
│   │   ├── tp_configs.py        # TP1–TP4 Konfigurationen (s.o.)
│   │   ├── agent_prompts/       # System-Prompts pro Agent × TP
│   │   │   ├── metacognitive_tp1.md
│   │   │   ├── metacognitive_tp2.md
│   │   │   ├── ...
│   │   │   ├── strategic_tp1.md
│   │   │   ├── ...
│   │   │   ├── conceptual_tp1.md
│   │   │   ├── ...
│   │   │   ├── procedural_tp1.md
│   │   │   └── ...
│   │   └── rubrics/             # Rubric-Daten (JSON)
│   │       ├── tp1_rubric.json
│   │       ├── tp2_rubric.json
│   │       ├── tp3_rubric.json
│   │       └── tp4_rubric.json
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── group.py             # Gruppen-Datenmodell
│   │   ├── message.py           # Nachrichten-Datenmodell
│   │   └── session.py           # Session-Datenmodell
│   │
│   └── data/
│       ├── on_case_v3/          # ON Running Case (Kapitel + Exhibits)
│       │   ├── chapter_a.md
│       │   ├── chapter_b.md
│       │   ├── chapter_c.md
│       │   ├── chapter_d.md
│       │   └── exhibits/
│       ├── tp_briefings/        # Studierenden-sichtbare Aufgabenstellungen
│       └── frameworks/          # BWL-Denkprinzipien (ohne Modellnamen)
│
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx         # Landing / Gruppenauswahl
│   │   │   ├── chat/
│   │   │   │   └── page.tsx     # Haupt-Chat-Interface
│   │   │   └── layout.tsx
│   │   ├── components/
│   │   │   ├── ChatWindow.tsx       # Chat mit Agent-Indikator
│   │   │   ├── TPProgress.tsx       # TP-Fortschrittsanzeige
│   │   │   ├── CaseReference.tsx    # ON-Case-Referenz-Panel
│   │   │   ├── GroupContext.tsx      # Gruppengedächtnis-Anzeige
│   │   │   └── ReflectionPrompt.tsx # Metacognitive Einstiegsfrage
│   │   ├── hooks/
│   │   │   ├── useChat.ts
│   │   │   └── useGroupMemory.ts
│   │   └── lib/
│   │       ├── api.ts
│   │       └── types.ts
│   └── public/
│
├── tests/
│   ├── test_orchestrator.py
│   ├── test_agents.py
│   ├── test_guardrails.py
│   └── test_rag.py
│
├── scripts/
│   ├── index_case.py            # Case-Dokumente indexieren
│   ├── setup_db.py              # Datenbank initialisieren
│   └── seed_groups.py           # Test-Gruppen anlegen
│
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── pyproject.toml
```

---

## Implementierungsreihenfolge

### Phase 1: Foundation (Woche 1–2)
1. **Backend-Skeleton** — FastAPI mit WebSocket-Support, Datenmodelle
2. **Base Agent** — abstrakte Basisklasse mit LLM-Anbindung
3. **Einfacher Orchestrator** — noch ohne Agenten-Routing, nur ein Agent
4. **RAG-Pipeline** — ON-Case indexieren, einfaches Retrieval
5. **Minimales Frontend** — Chat-UI mit Gruppen-Login

### Phase 2: Agenten (Woche 3–4)
6. **Metacognitiver Agent** — System-Prompts für TP1–TP4
7. **Strategischer Agent** — mit impliziter Framework-Steuerung
8. **Konzeptueller Agent** — mit TP-weiser Kapitel-Freischaltung
9. **Prozeduraler Agent** — formatspezifische Hilfe
10. **Agent-Routing** im Orchestrator — Intent-Klassifikation

### Phase 3: Intelligenz (Woche 5–6)
11. **Guardrail Layer** — Answer-Filter, Framework-Filter, Phase-Filter
12. **Gruppengedächtnis** — TP-Ergebnisse persistieren, Rückverweise
13. **Metacognitive-First-Sequenzierung** — automatische Reflexionsphase
14. **Scaffolding-Intensität** — adaptiv basierend auf Gruppenfortschritt

### Phase 4: Polish (Woche 7–8)
15. **Frontend-Features** — TP-Fortschritt, Case-Referenz-Panel, Gruppensicht
16. **Logging & Analytics** — Interaktionsdaten für Forschung
17. **Testing & Kalibrierung** — Prompt-Tuning, Guardrail-Schwellwerte
18. **Deployment** — Docker, CI/CD, Monitoring

---

## Coding-Konventionen

### Python (Backend)
- Python 3.11+
- FastAPI + Pydantic v2 für Validierung
- async/await durchgängig
- Type Hints überall
- Docstrings im Google-Style
- Tests mit pytest + pytest-asyncio
- Logging mit structlog

### TypeScript (Frontend)
- Next.js 14+ (App Router)
- TypeScript strict mode
- Tailwind CSS
- Zustand für State Management
- React Query für Server State

### Prompts
- System-Prompts als Markdown-Dateien in `/backend/config/agent_prompts/`
- Jeder Prompt ist benannt: `{agent_type}_tp{n}.md`
- Prompts enthalten: Rollenanweisung, TP-spezifische Constraints, Beispiel-Interaktionen, Verbotsliste

### Datenbank
- PostgreSQL für Gruppendaten, Sessions, Konversationen
- ChromaDB / Pinecone für RAG-Vektoren
- Redis für Session-Cache

---

## Kritische Design-Entscheidungen

### Warum nicht das bestehende MAS fork-en?
Das bestehende MAS (github.com/koizachek/scaffolding_multiagentsystem) ist für **Einzelpersonen** in **einmaligen Concept-Mapping-Sessions** gebaut. BWL A braucht:
- **Gruppenkontext** statt Einzelprofil
- **Longitudinaler Verlauf** (4 TPs über ein Semester) statt einer Session
- **Wechselnde Abgabeformate** statt Concept Maps
- **Implizite Framework-Steuerung** (Anti-Framework-Dropping)
- **Constructive-Alignment-Einbettung** mit Bloom-Progression

Was wir **übernehmen**: Das Metacognitive-First-Prinzip, die 4-Agenten-Taxonomie (metacognitiv, strategisch, konzeptuell, prozedural), die Scaffolding-Intensitäts-Logik (high/medium/low), das Conversation-Logging-Format.

### Warum "zwischen" den Touchpoints?
Die Präsenzsitzungen (90 Min pro TP) sind bewusst analog: Präsentationen, Diskussion, handschriftliche Reflexionskarten. Das System unterstützt die **Vorbereitung** (Case lesen, Abgabe erstellen) und die **Nachbereitung** (Reflexion, Transfer zum nächsten TP). Es ist kein Ersatz für die Präsenzlehre.

### Warum keine automatische Bewertung?
Das Lehrdesign setzt auf **pfadoffene Rubrics** — es gibt keine Musterlösungen. Automatisches Grading würde dem Anti-Pattern-Design widersprechen. Das System kann aber **formatives Feedback** geben: "Eure Wirkungskette hat drei Schritte — fehlt da noch etwas zwischen Ursache und Handlungsdruck?"

---

## Guardrails — Die wichtigsten Regeln

1. **NIEMALS** direkte Antworten geben ("Die zwei kritischsten Herausforderungen sind...")
2. **NIEMALS** Framework-Namen nennen ("Benutzt Porter's Five Forces")
3. **NIEMALS** Textbausteine oder Formulierungsvorschläge liefern
4. **NIEMALS** auf NORDIC HOME oder den Klausur-Case verweisen
5. **NIEMALS** Rubric-Punktzahlen oder Bewertungskriterien für Dozierende offenlegen
6. **IMMER** mit einer Frage antworten, die zum Weiterdenken anregt
7. **IMMER** auf den ON-Case als Evidenzquelle verweisen
8. **IMMER** die Gruppe ermutigen, ihre eigene Argumentationslogik zu entwickeln
9. **IMMER** Konsistenz zwischen TPs einfordern (ab TP2)
10. **IMMER** mit metacognitiver Reflexion beginnen (pro Session)

---

## Prompt-Templates — Beispielstruktur

### Metacognitiver Agent, TP2

```markdown
Du bist ein metacognitiver Lernbegleiter für eine Gruppe von Studierenden,
die an Touchpoint 2 des BWL-A-Kurses der Universität St.Gallen arbeiten.

## Deine Rolle
Du hilfst der Gruppe, ihren Denkprozess zu reflektieren und zu planen.
Du gibst KEINE inhaltlichen Antworten. Du stellst Fragen, die zum
Nachdenken anregen.

## TP2-Kontext
Die Gruppe hat in TP1 eine Situationsanalyse erstellt (Herausforderungen,
Wirkungsketten, Stakeholder). Jetzt sollen sie eine strategische
Entscheidung treffen: Wie soll ON wachsen und sich positionieren?

## Was du TUST
- Frage nach dem Plan: "Wie wollt ihr vorgehen? Was ist euer erster Schritt?"
- Frage nach Unsicherheiten: "Wo fühlt ihr euch am unsichersten?"
- Verweise auf TP1: "Wie passt eure Strategie zu den Herausforderungen,
  die ihr in TP1 identifiziert habt?"
- Frage nach Trade-offs: "Was gewinnt ihr mit dieser Richtung? Was gebt ihr auf?"
- Frage nach Steuerung: "Woran würdet ihr erkennen, dass die Strategie funktioniert?"

## Was du NICHT tust
- Keine Strategie empfehlen
- Keine Modellnamen nennen (kein "Porter", "RBV", "VRIO", "Five Forces")
- Keine Bewertung der Qualität der Arbeit abgeben
- Keine Textvorschläge machen
- Nicht auf TP3 oder TP4 vorgreifen

## Gruppengedächtnis
{group_memory}

## Gesprächsverlauf
{conversation_history}
```

---

## Testing-Strategie

### Unit Tests
- Agent-Responses: Enthalten sie keine verbotenen Framework-Namen?
- Guardrails: Filtern sie direkte Antworten korrekt?
- Orchestrator: Routet er zum richtigen Agenten?
- RAG: Liefert er nur TP-freigeschaltete Kapitel?

### Integration Tests
- Vollständige Konversation: Metacognitive → Strategic → Conceptual → Procedural
- TP-Übergang: Gruppengedächtnis wird korrekt übertragen
- Guardrail-Cascade: Mehrere Filter hintereinander

### Smoke Tests (mit echten LLM-Calls)
- 10 typische Studierenden-Fragen pro TP
- Prüfe: Keine direkten Antworten? Keine Framework-Namen? Sokratische Fragen?
- Prüfe: Konsistenz-Rückverweise auf vorherige TPs?

---

## Geklärte Design-Entscheidungen

### 1. Authentifizierung — Standalone first, SSO later
- **Proof-of-Concept:** Einfacher Gruppencode + individuelle User-IDs (kein SSO)
- Gruppen werden per Seed-Script angelegt, jedes Mitglied erhält einen Login-Link
- HSG-SSO-Integration erst nach validiertem PoC

### 2. Multi-User — Ganze Gruppe gleichzeitig
- **Alle 6 Mitglieder können gleichzeitig im selben Chat interagieren**
- Jede Nachricht ist mit dem User-Namen getaggt (sichtbar für alle)
- Das System antwortet der Gruppe, nicht Einzelpersonen
- Verhindert, dass nur eine Person die Arbeit macht
- **Technisch:** WebSocket-basierter Gruppenchat mit Presence-Indikator ("Lisa, Max und Kai sind online")
- Implementierung analog zu einem einfachen Gruppenchat, aber mit AI-Agent statt Peer-to-Peer

### 3. TP-Phasen — Globaler Zyklus per Deadline
- Alle Gruppen sind zur selben Zeit in derselben TP-Phase
- TP-Wechsel erfolgt automatisch per konfigurierter Deadline im Admin-Panel
- Kein manueller Eingriff pro Gruppe nötig
- Deadlines werden im System als globale Config gespeichert:
```python
TP_SCHEDULE = {
    1: {"start": "2026-09-14", "deadline": "2026-10-05"},
    2: {"start": "2026-10-06", "deadline": "2026-10-26"},
    3: {"start": "2026-10-27", "deadline": "2026-11-16"},
    4: {"start": "2026-11-17", "deadline": "2026-12-07"},
}
```

### 4. Dozierende — Insights ja, Logs nein
- **Dozierenden-Dashboard** zeigt aggregierte Insights pro Übungsgruppe:
  - Welche Themen werden am häufigsten diskutiert?
  - Wo stecken Gruppen fest? (häufige Rückfragen, lange Sessions ohne Fortschritt)
  - Welche Frameworks werden (implizit) am wenigsten angewandt?
  - Gruppenaktivität: Wer interagiert wie oft?
- **Keine** Einsicht in Konversationslogs oder Agent-Antworten
- Dozierende sehen **keine** individuellen Chat-Verläufe

### 5. Forschungsdaten — Comprehensive Logging (nur für Forschende)
Analoges Logging-Design wie im bestehenden MAS-Prototypen:

```python
class ResearchLogger:
    """Loggt alle Interaktionsdaten für wissenschaftliche Auswertung.
    Nur für Forschende zugänglich, NICHT für Dozierende."""
    
    def log_event(self, event_type: str, metadata: dict):
        """Events: message_sent, agent_response, agent_routed,
        guardrail_triggered, session_started, session_ended,
        tp_phase_changed, group_memory_updated"""
        pass
    
    # Was geloggt wird:
    # - Vollständige Konversationshistorie (user + agent, mit Timestamps)
    # - Agent-Routing-Entscheidungen (welcher Agent, warum)
    # - Guardrail-Auslösungen (was gefiltert wurde)
    # - Scaffolding-Intensitäts-Änderungen
    # - Gruppengedächtnis-Snapshots bei jedem TP-Übergang
    # - User-Aktivitätsmuster (wer chattet wann, wie oft)
    # - Session-Metriken (Dauer, Nachrichten-Count, Agents-Used)
```

**Export-Formate:**
- JSON (vollständige Session-Daten)
- CSV (für statistische Analyse)
- Strukturierte DB-Queries (PostgreSQL)

**Speicherorte:**
- Real-time: `/logs/` (detaillierte Events)
- Session-Completion: `/research_data/` (aggregierte Forschungsdaten)
- DB: PostgreSQL (strukturierte Queries)

### 6. Skalierung
- ~330 Gruppen × 6 Mitglieder = ~2.000 User
- Peak-Load vor Deadlines: potentiell 200+ gleichzeitige Gruppen
- **Architektur:** Stateless Backend hinter Load Balancer, WebSocket-Connections per Group-Room
- **LLM-API:** Rate Limiting + Queue für API-Calls, Retry-Logic
- **DB:** Connection Pooling, Read Replicas für Dashboard-Queries

### 7. Internationalisierung — DE + EN, umschaltbar
- Sprache ist pro Gruppe konfigurierbar (Setting beim Erstellen)
- Einzelne User können in der UI umschalten (betrifft UI-Labels)
- **Agent-Antworten** passen sich an die Gruppensprache an (System-Prompt-Variable)
- **Case-Material** liegt auf Deutsch vor; englische Interaktion referenziert trotzdem den deutschen Case
- **i18n-Implementierung:** next-intl (Frontend), Prompt-Templates mit `{language}` Variable (Backend)

---

## Verzeichnisstruktur (aktualisiert)

Die Verzeichnisstruktur oben wird um folgende Komponenten ergänzt:

```
ToAdapt/
├── ...                          # (wie oben)
├── backend/
│   ├── ...                      # (wie oben)
│   ├── realtime/
│   │   ├── __init__.py
│   │   ├── websocket.py         # WebSocket-Manager für Gruppenchats
│   │   ├── presence.py          # Online-Status pro Gruppe
│   │   └── broadcast.py         # Nachrichten an alle Gruppenmitglieder
│   │
│   ├── dashboard/
│   │   ├── __init__.py
│   │   ├── aggregator.py        # Aggregierte Insights berechnen
│   │   ├── routes.py            # Dashboard-API-Endpoints
│   │   └── models.py            # Dashboard-Datenmodelle
│   │
│   ├── research/
│   │   ├── __init__.py
│   │   ├── logger.py            # ResearchLogger (comprehensive)
│   │   ├── exporter.py          # JSON/CSV-Export
│   │   └── analytics.py         # Forschungsmetriken berechnen
│   │
│   └── i18n/
│       ├── __init__.py
│       ├── de.json              # Deutsche UI-Strings
│       └── en.json              # Englische UI-Strings
│
├── frontend/
│   ├── ...                      # (wie oben)
│   ├── src/
│   │   ├── components/
│   │   │   ├── ...              # (wie oben)
│   │   │   ├── PresenceBar.tsx  # "Lisa, Max und Kai sind online"
│   │   │   ├── MessageBubble.tsx # Chat-Bubble mit Username-Tag
│   │   │   └── LanguageSwitch.tsx
│   │   └── i18n/
│   │       ├── de.json
│   │       └── en.json
│   │
│   └── dashboard/               # Separates Dozierenden-Frontend
│       ├── page.tsx             # Dashboard-Hauptseite
│       ├── components/
│       │   ├── TopicHeatmap.tsx  # Welche Themen werden diskutiert?
│       │   ├── StuckGroups.tsx   # Wo stecken Gruppen fest?
│       │   └── ActivityChart.tsx # Gruppenaktivität über Zeit
│       └── ...
```
