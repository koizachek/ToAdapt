"""Tests für das Case-Paket (eingebettete Rubric + zweistufige Kalibrierungsanker).

Kern: Der Golden Case (alpes-bank-genai-001) muss sich nach der Migration
EXAKT gleich verhalten wie vorher (Datei-Rubric + hartkodierte Anker) —
sonst wäre die Teacher-Alignment-Studie invalidiert.
"""

import json

import pytest

from backend.cases.generator import CaseGenerator
from backend.cases.manager import case_manager
from backend.cases.validator import validate_case
from backend.evaluator.rubric_evaluator import BLOOM_CALIBRATION_ANCHORS, RubricEvaluator
from backend.evaluator.rubric_loader import RUBRICS_DIR, load_question_rubric
from backend.models.case import CanvasBlockSpec, CaseQuestion

GOLDEN_CASE = "alpes-bank-genai-001"


@pytest.fixture(autouse=True)
def no_mongo(monkeypatch):
    for var in ("MONGODB_URI", "MONGODB_MAS_NAME", "MONGODB_MAS_KEY", "MONGODB_HOST"):
        monkeypatch.delenv(var, raising=False)


# ---------------------------------------------------------------------------
# Äquivalenz: eingebettete Rubric == Datei-Rubric (Golden Case)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case_id", [GOLDEN_CASE, f"{GOLDEN_CASE}-en"])
def test_golden_case_embedded_rubric_equals_file_rubric(case_id):
    case = case_manager.get(case_id)
    assert case is not None
    for question in case.questions:
        embedded = load_question_rubric(question)
        assert embedded is not None

        payload = json.loads((RUBRICS_DIR / question.rubric_reference).read_text(encoding="utf-8"))
        file_data = payload["questions"].get(question.question_id) or payload["default"]

        assert embedded.evaluation_focus == file_data["evaluation_focus"]
        assert [b.model_dump() for b in embedded.required_canvas_blocks] == [
            {"weight": 1.0, **fb} for fb in file_data["required_canvas_blocks"]
        ]
        assert embedded.exemplar_threshold_pct == file_data.get("exemplar_threshold_pct", 80.0)
        assert embedded.score_floor_pct == file_data.get("score_floor_pct", 75.0)


def test_golden_case_calibration_notes_unchanged():
    """Die per Studie validierten Anker müssen wörtlich erhalten bleiben."""
    case = case_manager.get(GOLDEN_CASE)
    evaluator = RubricEvaluator(api_key="test-key")

    q1 = next(q for q in case.questions if q.question_id == "q1")
    notes = evaluator._format_calibration_notes(q1)
    assert "zwei klar getrennte Herausforderungen" in notes

    q4 = next(q for q in case.questions if q.question_id == "q4")
    notes4 = evaluator._format_calibration_notes(q4)
    assert "frühere Entscheidungen integriert" in notes4
    # Generische Bloom-Anker dürfen NICHT zusätzlich einfließen (Prompt-Drift)
    assert "Kaskadenlogik" not in notes4


# ---------------------------------------------------------------------------
# Zweistufige Anker: generierte Cases erben NICHT mehr die Alpes-Anker
# ---------------------------------------------------------------------------

def _question(**overrides) -> CaseQuestion:
    defaults = dict(
        question_id="q1", phase=2, bloom_level=5, text="Frage?",
        max_points=10, rubric_reference="tp2_rubric.json",
    )
    defaults.update(overrides)
    return CaseQuestion(**defaults)


def test_generic_bloom_anchors_for_uncalibrated_questions():
    evaluator = RubricEvaluator(api_key="test-key")
    notes = evaluator._format_calibration_notes(_question(bloom_level=6, question_id="q4"))
    # Generischer Bloom-6-Anker, NICHT der Alpes-q4-Anker
    assert "Synthese" in notes
    assert "frühere Entscheidungen integriert" not in notes
    assert "Use Cases" not in notes  # Alpes-q2-Vokabular darf nicht auftauchen


def test_bloom_anchors_cover_all_levels():
    assert set(BLOOM_CALIBRATION_ANCHORS.keys()) == {2, 3, 4, 5, 6}


def test_embedded_rubric_takes_precedence_over_file():
    question = _question(
        rubric_reference="tp1_rubric.json",  # Datei existiert und wäre Alpes-kalibriert
        evaluation_focus=["Eigenes Kriterium"],
        required_canvas_blocks=[CanvasBlockSpec(
            block="channels", label="Channels",
            accepted_keywords=["vertriebskanal"], expectation="Kanalwirkung zeigen",
        )],
        exemplar_threshold_pct=90.0,
    )
    rubric = load_question_rubric(question)
    assert rubric.evaluation_focus == ["Eigenes Kriterium"]
    assert rubric.required_canvas_blocks[0].block == "channels"
    assert rubric.exemplar_threshold_pct == 90.0
    assert rubric.score_floor_pct == 75.0  # None → Default


def test_file_fallback_still_works_without_embedded_package():
    rubric = load_question_rubric(_question(question_id="q1", rubric_reference="tp1_rubric.json"))
    assert rubric is not None
    assert rubric.required_canvas_blocks  # Alpes-Datei-Inhalt


# ---------------------------------------------------------------------------
# Validator + Generator
# ---------------------------------------------------------------------------

def test_validator_warns_when_embedded_rubric_missing():
    case = case_manager.get(GOLDEN_CASE)
    case.questions[0].required_canvas_blocks = []
    report = validate_case(case)
    assert any(i.code == "missing_embedded_rubric" for i in report.issues)


async def test_generator_parses_embedded_package(monkeypatch):
    draft_json = json.dumps({
        "title": "Nordwind Logistik — Test",
        "tagline": "Ein Test-Case.",
        "glossary": [{
            "term": "Zielgruppe",
            "explanation": "Die Kundengruppe, auf die sich ein Angebot richtet.",
            "starter_prompt": "Erkläre mir kurz den Begriff \"Zielgruppe\".",
        }],
        "agent_guidance": {
            "case_summary": "Ein Logistiker unter Preisdruck.",
            "key_tensions": ["Wachstum vs. Marge"],
            "common_mistakes": ["Preissenkung ohne Kostenblick"],
        },
        "sections": [{"section_id": "s1", "title": "Start", "content": "Text zur Zielgruppe."}],
        "exhibits": [{"exhibit_id": "e1", "title": "Zahlen", "content": "| a |", "exhibit_type": "table"}],
        "questions": [{
            "question_id": "q1", "phase": 1, "bloom_level": 2, "text": "Frage?",
            "max_points": 25, "rubric_reference": "tp1_rubric.json",
            "allowed_frameworks": [], "forbidden_framework_names": [],
            "evaluation_focus": ["Kriterium A"],
            "required_canvas_blocks": [{
                "block": "customer_segments", "label": "Customer Segments",
                "accepted_keywords": ["zielgruppe", "kundensegment"],
                "expectation": "Segmente benennen", "weight": 1.0,
            }],
            "min_words": 60, "max_words": 180,
        }],
    })

    async def fake_complete(self, *, system, messages, max_tokens):
        return draft_json

    monkeypatch.setattr("backend.llm.OpenRouterClient.complete", fake_complete)

    generator = CaseGenerator(api_key="test-key")
    result = await generator.generate_draft(
        industry="Logistics", country="Deutschland", target_tp=1,
    )
    q = result.questions[0]
    assert q.evaluation_focus == ["Kriterium A"]
    assert q.required_canvas_blocks[0].accepted_keywords == ["zielgruppe", "kundensegment"]
    assert (q.min_words, q.max_words) == (60, 180)
    assert result.glossary[0].term == "Zielgruppe"
    assert result.agent_guidance.key_tensions == ["Wachstum vs. Marge"]


# ---------------------------------------------------------------------------
# Agent-Guidance: Case-Paket vor Pool-Datei
# ---------------------------------------------------------------------------

def test_orchestrator_guidance_prefers_embedded(monkeypatch, tmp_path):
    import backend.cases.manager as manager_module
    from backend.agents.orchestrator import _load_case_guidance
    from backend.models.case import AgentGuidance, Case

    monkeypatch.setattr(manager_module, "POOL_DIR", tmp_path)
    case = Case(
        case_id="embedded-guidance-001", title="T", industry="X", country="DE",
        tagline="t", difficulty="tp1", target_tp=1,
        agent_guidance=AgentGuidance(
            key_tensions=["Tempo vs. Qualität"],
            common_mistakes=["Nur eine Option prüfen"],
        ),
    )
    manager_module.case_manager.save(case)

    guidance = _load_case_guidance("embedded-guidance-001")
    assert "Tempo vs. Qualität" in guidance
    assert "KERN-SPANNUNGSFELDER" in guidance


def test_orchestrator_guidance_file_fallback_for_golden_case():
    from backend.agents.orchestrator import _load_case_guidance

    guidance = _load_case_guidance(GOLDEN_CASE)
    assert "KERN-SPANNUNGSFELDER" in guidance  # aus der -agent.json-Pool-Datei


def test_validator_warns_on_missing_glossary_and_guidance():
    case = case_manager.get(GOLDEN_CASE)
    report = validate_case(case)
    codes = {i.code for i in report.issues}
    # Golden Case nutzt Frontend-/Datei-Fallbacks → Warnungen, aber kein Fehler
    assert "no_glossary" in codes and "no_agent_guidance" in codes
    assert report.ok


def test_validator_warns_on_glossary_term_missing_in_text():
    case = case_manager.get(GOLDEN_CASE)
    from backend.models.case import GlossaryTermSpec
    case.glossary = [GlossaryTermSpec(term="Kommt-nicht-vor", explanation="x", starter_prompt="y")]
    report = validate_case(case)
    assert any(i.code == "glossary_term_not_in_text" for i in report.issues)
