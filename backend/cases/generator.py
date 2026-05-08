"""Case-Generator — AI-Draft-Pipeline für Mini-Cases.

Workflow:
    1. Dozent wählt: Branche, Land, TP-Ziel, Schwierigkeit
    2. Generator erstellt vollständigen Case (Sections + Exhibits + Questions)
    3. Case landet mit status=DRAFT im Pool
    4. Dozent reviewed und approved/rejected im Admin-Interface
"""

import json
import uuid
from datetime import datetime

import structlog

from backend.config.tp_configs import TP_CONFIGS
from backend.llm import OpenRouterClient
from backend.models.case import (
    Case,
    CaseDifficulty,
    CaseExhibit,
    CaseQuestion,
    CaseSection,
    CaseStatus,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Prompt-Templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Du bist ein erfahrener BWL-Dozent an der Universität St. Gallen.
Du erstellst Mini-Cases für einen Transfer-Trainer in BWL A.

WICHTIGE REGELN:
- Der Case basiert NICHT auf ON Running und NICHT auf NORDIC HOME (diese sind für den echten Kurs reserviert).
- Das Unternehmen ist fiktiv. Alle Zahlen, Namen und Personen sind erfunden.
- Der Case ist in sich geschlossen — kein Vorwissen nötig.
- Frameworks werden NIE beim Namen genannt. Stattdessen wird ihre Logik implizit erzwungen.
- Keine "richtigen" Lösungen — mehrere vertretbare Antwortpfade sind möglich.
- Sprache: Deutsch, managementnah, präzise.

Du antwortest AUSSCHLIESSLICH mit einem validen JSON-Objekt. Kein Text davor oder danach."""

CASE_GENERATION_PROMPT = """Erstelle einen vollständigen Mini-Case für den Transfer-Trainer.

Parameter:
- Branche: {industry}
- Herkunftsland: {country}
- Ziel-TP: {target_tp} ({tp_name})
- Schwierigkeit: {difficulty}
- Bloom-Stufen: {bloom_levels}

Erlaubte Framework-Logiken (implizit einzubauen, nicht namentlich nennen):
{allowed_frameworks}

Verbotene Framework-Namen (dürfen nicht im Text erscheinen):
{forbidden_framework_names}

Erstelle einen Case mit diesem exakten JSON-Schema:
{{
  "title": "Firmenname — kurzer Untertitel",
  "tagline": "Ein-Satz-Beschreibung des Unternehmens und seiner Herausforderung",
  "sections": [
    {{
      "section_id": "s1",
      "title": "Abschnittstitel",
      "content": "2–4 Paragraphen Fließtext"
    }}
  ],
  "exhibits": [
    {{
      "exhibit_id": "e1",
      "title": "Exhibit-Titel",
      "content": "Markdown-Tabelle oder Freitext",
      "exhibit_type": "table"
    }}
  ],
  "questions": [
    {{
      "question_id": "q1",
      "phase": {target_tp},
      "bloom_level": 3,
      "text": "Fragestellung für den Studierenden",
      "max_points": 9,
      "rubric_reference": "tp{target_tp}_rubric.json",
      "allowed_frameworks": ["..."],
      "forbidden_framework_names": ["..."]
    }}
  ]
}}

Anforderungen:
- 4–6 Sections (narrative, verdichtet, mit echten Spannungsfeldern)
- 3–5 Exhibits (mind. 1 Datentabelle, mind. 1 Zitat einer Managerin/eines Managers)
- {num_questions} Fragen, die exakt die Bloom-Stufen {bloom_levels} abdecken
- Jede Frage impliziert ein Framework, nennt es aber nicht
- Gesamtpunktzahl aller Fragen: {total_points}
- Case-Länge: entspricht ca. {page_count} Seiten A4"""


# ---------------------------------------------------------------------------
# TP-spezifische Generierungs-Parameter
# ---------------------------------------------------------------------------

TP_GENERATION_PARAMS: dict[int, dict] = {
    1: {"num_questions": 3, "total_points": 25, "page_count": "4–5"},
    2: {"num_questions": 3, "total_points": 24, "page_count": "4–5"},
    3: {"num_questions": 4, "total_points": 22, "page_count": "5–6"},
    4: {"num_questions": 3, "total_points": 30, "page_count": "6–7"},
}


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class CaseGenerator:
    def __init__(self, api_key: str):
        self.client = OpenRouterClient(api_key=api_key)

    async def generate_draft(
        self,
        industry: str,
        country: str,
        target_tp: int,
        difficulty: str = CaseDifficulty.TP1,
    ) -> Case:
        """Erstellt einen AI-generierten Case-Draft."""

        tp_cfg = TP_CONFIGS[target_tp]
        gen_params = TP_GENERATION_PARAMS[target_tp]

        prompt = CASE_GENERATION_PROMPT.format(
            industry=industry,
            country=country,
            target_tp=target_tp,
            tp_name=tp_cfg["name"],
            difficulty=difficulty,
            bloom_levels=tp_cfg["bloom_levels"],
            allowed_frameworks="\n".join(f"- {f}" for f in tp_cfg["allowed_frameworks"]),
            forbidden_framework_names=", ".join(tp_cfg["forbidden_framework_names"]),
            num_questions=gen_params["num_questions"],
            total_points=gen_params["total_points"],
            page_count=gen_params["page_count"],
        )

        logger.info("case_generation_started", industry=industry, country=country, tp=target_tp)

        raw = await self.client.complete(
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
        data = json.loads(raw)

        case = Case(
            case_id=str(uuid.uuid4()),
            title=data["title"],
            industry=industry,
            country=country,
            tagline=data["tagline"],
            difficulty=difficulty,
            target_tp=target_tp,
            sections=[CaseSection(**s) for s in data["sections"]],
            exhibits=[CaseExhibit(**e) for e in data["exhibits"]],
            questions=[CaseQuestion(**q) for q in data["questions"]],
            status=CaseStatus.DRAFT,
            generated_by="ai",
            created_at=datetime.utcnow(),
        )

        logger.info("case_generation_complete", case_id=case.case_id, title=case.title)
        return case
