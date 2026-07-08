from backend.evaluator.rubric_evaluator import RubricEvaluator
from backend.models.case import Case, CaseQuestion
from backend.models.submission import QuestionScore, Submission


def test_extracts_plain_json():
    evaluator = RubricEvaluator.__new__(RubricEvaluator)
    payload = evaluator._parse_evaluation_payload(
        '{"awarded_points": 10, "feedback": "ok", "learning_objective_tags": ["analyse"]}',
        ["analyse"],
    )
    assert payload["awarded_points"] == 10


def test_extracts_fenced_json():
    evaluator = RubricEvaluator.__new__(RubricEvaluator)
    payload = evaluator._parse_evaluation_payload(
        '```json\n{"awarded_points": 7, "feedback": "ok", "learning_objective_tags": ["transfer"]}\n```',
        ["transfer"],
    )
    assert payload["awarded_points"] == 7


def test_extracts_json_from_wrapped_text():
    evaluator = RubricEvaluator.__new__(RubricEvaluator)
    payload = evaluator._parse_evaluation_payload(
        'Hier ist das Ergebnis:\n{"awarded_points": 5, "feedback": "ok", "learning_objective_tags": ["kpi"]}',
        ["kpi"],
    )
    assert payload["awarded_points"] == 5


def test_sanitize_feedback_removes_answer_templates():
    evaluator = RubricEvaluator.__new__(RubricEvaluator)
    feedback = evaluator._sanitize_feedback(
        "Erste Herausforderung könnte sein, dass Tamara den Website-Chatbot wählen sollte.",
    )
    assert "erste herausforderung könnte sein" not in feedback.lower()
    assert "wählen sollte" not in feedback.lower()


def test_sanitize_canvas_rationale_removes_case_speculation():
    evaluator = RubricEvaluator.__new__(RubricEvaluator)
    rationale = evaluator._sanitize_canvas_rationale(
        "FINMA-konformes Swiss Hosting auf Azure Switzerland wäre hier zentral."
    )
    assert rationale == (
        "Die Begründung bleibt bei den im Case sichtbaren Hinweisen und vermeidet nicht belegte Zusatzdetails."
    )


def test_fallback_payload_marks_human_review():
    evaluator = RubricEvaluator.__new__(RubricEvaluator)
    payload = evaluator._fallback_payload(["analyse"])

    assert payload["evaluation_status"] == "technical_fallback"
    assert payload["needs_human_review"] is True
    assert payload["judge_confidence"] == "low"


def test_result_from_scores_recomputes_totals():
    evaluator = RubricEvaluator.__new__(RubricEvaluator)
    case = Case(
        case_id="case-1",
        title="Case",
        industry="Banking",
        country="CH",
        tagline="Tagline",
        difficulty="tp1",
        target_tp=1,
        questions=[
            CaseQuestion(
                question_id="q1",
                phase=1,
                bloom_level=4,
                text="Question 1",
                max_points=10,
                rubric_reference="",
            ),
            CaseQuestion(
                question_id="q2",
                phase=2,
                bloom_level=5,
                text="Question 2",
                max_points=20,
                rubric_reference="",
            ),
        ],
    )
    submission = Submission(
        submission_id="sub-1",
        user_id="user-1",
        matrikelnummer="pid-1",
        case_id="case-1",
        target_tp=1,
    )
    scores = [
        QuestionScore(
            question_id="q1",
            bloom_level=4,
            max_points=10,
            awarded_points=5,
            feedback="ok",
            learning_objective_tags=["analyse"],
            canvas_alignment_score=0.5,
        ),
        QuestionScore(
            question_id="q2",
            bloom_level=5,
            max_points=20,
            awarded_points=10,
            feedback="ok",
            learning_objective_tags=["analyse"],
            canvas_alignment_score=1.0,
        ),
    ]

    result = evaluator.result_from_scores(submission=submission, case=case, scores=scores)

    assert result.total_points == 15
    assert result.max_points == 30
    assert result.percentage == 50
    assert result.canvas_alignment_pct == 83.3


# ---------------------------------------------------------------------------
# Robustheits-Kette und Parallelisierung (nach Rework 2026-07-09)
# ---------------------------------------------------------------------------

def _mini_case() -> Case:
    return Case(
        case_id="case-r", title="Case R", industry="Retail", country="DE",
        tagline="t", difficulty="tp1", target_tp=1,
        questions=[
            CaseQuestion(question_id="q1", phase=1, bloom_level=4, text="F1?",
                         max_points=10, rubric_reference=""),
            CaseQuestion(question_id="q2", phase=1, bloom_level=5, text="F2?",
                         max_points=20, rubric_reference=""),
        ],
    )


def _mini_submission(answers: dict) -> Submission:
    return Submission(submission_id="sub-r", user_id="u", matrikelnummer="m",
                      case_id="case-r", target_tp=1, answers=answers)


def _valid_payload(points: float) -> str:
    import json as _json
    return _json.dumps({
        "awarded_points": points, "feedback": "Solider Ansatz — was folgt daraus?",
        "learning_objective_tags": ["analyse"], "canvas_alignment_score": 0.5,
        "addressed_canvas_blocks": [], "missing_canvas_blocks": [],
        "judge_confidence": "high", "score_band": "solid",
        "main_strengths": [], "main_penalties": [], "needs_human_review": False,
    })


async def test_repair_call_recovers_invalid_first_response(monkeypatch):
    calls = []

    async def fake_complete(self, *, system, messages, max_tokens):
        calls.append(len(messages))
        if len(calls) == 1:
            return "Hier ist keine JSON-Antwort."
        return _valid_payload(7)

    monkeypatch.setattr("backend.llm.OpenRouterClient.complete", fake_complete)
    evaluator = RubricEvaluator(api_key="test")
    score, _ = await evaluator.evaluate_question(
        submission=_mini_submission({"q1": "Antwort."}), case=_mini_case(),
        question_id="q1", answer_text="Antwort.",
    )
    assert score.awarded_points == 7
    assert score.evaluation_status == "ok"
    assert len(calls) == 2  # Erst-Call + Repair-Call


async def test_invalid_number_types_fall_back_to_technical_fallback(monkeypatch):
    async def fake_complete(self, *, system, messages, max_tokens):
        return '{"awarded_points": "acht", "feedback": "ok", "canvas_alignment_score": 0.5}'

    monkeypatch.setattr("backend.llm.OpenRouterClient.complete", fake_complete)
    evaluator = RubricEvaluator(api_key="test")
    score, _ = await evaluator.evaluate_question(
        submission=_mini_submission({"q1": "Antwort."}), case=_mini_case(),
        question_id="q1", answer_text="Antwort.",
    )
    assert score.evaluation_status == "technical_fallback"
    assert score.awarded_points == 0.0
    assert score.needs_human_review is True


async def test_evaluate_submission_parallel_keeps_order(monkeypatch):
    async def fake_complete(self, *, system, messages, max_tokens):
        points = 5 if "F1?" in messages[0]["content"] else 15
        return _valid_payload(points)

    monkeypatch.setattr("backend.llm.OpenRouterClient.complete", fake_complete)
    evaluator = RubricEvaluator(api_key="test")
    result = await evaluator.evaluate_submission(
        _mini_submission({"q1": "A1.", "q2": "A2.", "q3": "   "}), _mini_case(),
    )
    assert [s.question_id for s in result.scores] == ["q1", "q2"]  # leere q3 übersprungen
    assert result.total_points == 20
    assert result.max_points == 30


def test_build_prompt_pins_band_anchors_and_calibration():
    from backend.cases.manager import case_manager

    evaluator = RubricEvaluator.__new__(RubricEvaluator)
    case = case_manager.get("alpes-bank-genai-001")
    q1 = next(q for q in case.questions if q.question_id == "q1")
    prompt = evaluator._build_prompt(
        case=case, question=q1, rubric=None,
        tags=["analysieren"], answer_text="X",
    )
    assert "- 13.8 Punkte:" in prompt   # 25 × 0.55, gerundet — Studien-Kalibrierung
    assert "- 6.2 Punkte:" in prompt    # 25 × 0.25
    assert "zwei klar getrennte Herausforderungen" in prompt
