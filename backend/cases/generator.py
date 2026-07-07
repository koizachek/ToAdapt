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
from backend.timeutils import naive_utcnow

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

SYSTEM_PROMPT = """Du bist ein erfahrener BWL-Dozent.
Du erstellst Mini-Cases für einen Transfer-Trainer in BWL A.

WICHTIGE REGELN:
- Der Case basiert NICHT auf ON Running und NICHT auf NORDIC HOME (diese sind für den echten Kurs reserviert).
- Das Unternehmen ist fiktiv. Alle Zahlen, Namen und Personen sind erfunden.
- Der Case ist in sich geschlossen — kein Vorwissen nötig.
- Frameworks werden NIE beim Namen genannt. Stattdessen wird ihre Logik implizit erzwungen.
- Keine "richtigen" Lösungen — mehrere vertretbare Antwortpfade sind möglich.
- Sprache: Deutsch, managementnah, präzise.

Du antwortest AUSSCHLIESSLICH mit einem validen JSON-Objekt. Kein Text davor oder danach."""

SYSTEM_PROMPT_EN = """You are an experienced business administration lecturer.
You create mini-cases for a business transfer trainer.

IMPORTANT RULES:
- The case is NOT based on ON Running and NOT on NORDIC HOME (these are reserved for the actual course).
- The company is fictional. All numbers, names, and people are invented.
- The case is self-contained and requires no prior knowledge.
- Frameworks are NEVER named directly. Instead, their logic is enforced implicitly.
- There are no single "correct" solutions. Several defensible answer paths are possible.
- Language: English, management-oriented, precise.

You respond ONLY with a valid JSON object. No text before or after it."""

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

CASE_GENERATION_PROMPT_EN = """Create a complete mini-case for the transfer trainer.

Parameters:
- Industry: {industry}
- Country of origin: {country}
- Target TP: {target_tp} ({tp_name})
- Difficulty: {difficulty}
- Bloom levels: {bloom_levels}

Allowed framework logics (build them in implicitly, do not name them):
{allowed_frameworks}

Forbidden framework names (must not appear in the text):
{forbidden_framework_names}

Create a case with this exact JSON schema:
{{
  "title": "Company name - short subtitle",
  "tagline": "One-sentence description of the company and its challenge",
  "sections": [
    {{
      "section_id": "s1",
      "title": "Section title",
      "content": "2-4 paragraphs of continuous text"
    }}
  ],
  "exhibits": [
    {{
      "exhibit_id": "e1",
      "title": "Exhibit title",
      "content": "Markdown table or continuous text",
      "exhibit_type": "table"
    }}
  ],
  "questions": [
    {{
      "question_id": "q1",
      "phase": {target_tp},
      "bloom_level": 3,
      "text": "Question for the student",
      "max_points": 9,
      "rubric_reference": "tp{target_tp}_rubric.json",
      "allowed_frameworks": ["..."],
      "forbidden_framework_names": ["..."]
    }}
  ]
}}

Requirements:
- 4-6 sections (narrative, concise, with real tensions)
- 3-5 exhibits (at least 1 data table, at least 1 quote from a manager)
- {num_questions} questions that cover exactly the Bloom levels {bloom_levels}
- Each question implies a framework but does not name it
- Total points across all questions: {total_points}
- Case length: approximately {page_count} A4 pages"""

TP_NAMES_EN = {
    1: "Analysis & stakeholders",
    2: "Strategic decision",
    3: "Translating strategy into the market",
    4: "Integration & overall picture",
}


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
        language: str = "de",
    ) -> Case:
        """Erstellt einen AI-generierten Case-Draft."""

        tp_cfg = TP_CONFIGS[target_tp]
        gen_params = TP_GENERATION_PARAMS[target_tp]
        prompt_template = CASE_GENERATION_PROMPT_EN if language == "en" else CASE_GENERATION_PROMPT
        system_prompt = SYSTEM_PROMPT_EN if language == "en" else SYSTEM_PROMPT
        tp_name = TP_NAMES_EN.get(target_tp, tp_cfg["name"]) if language == "en" else tp_cfg["name"]

        prompt = prompt_template.format(
            industry=industry,
            country=country,
            target_tp=target_tp,
            tp_name=tp_name,
            difficulty=difficulty,
            bloom_levels=tp_cfg["bloom_levels"],
            allowed_frameworks="\n".join(f"- {f}" for f in tp_cfg["allowed_frameworks"]),
            forbidden_framework_names=", ".join(tp_cfg["forbidden_framework_names"]),
            num_questions=gen_params["num_questions"],
            total_points=gen_params["total_points"],
            page_count=gen_params["page_count"],
        )

        logger.info("case_generation_started", industry=industry, country=country, tp=target_tp, language=language)

        raw = await self.client.complete(
            system=system_prompt,
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
            language=language,
            sections=[CaseSection(**s) for s in data["sections"]],
            exhibits=[CaseExhibit(**e) for e in data["exhibits"]],
            questions=[CaseQuestion(**q) for q in data["questions"]],
            status=CaseStatus.DRAFT,
            generated_by="ai",
            created_at=naive_utcnow(),
        )

        logger.info("case_generation_complete", case_id=case.case_id, title=case.title, language=language)
        return case
