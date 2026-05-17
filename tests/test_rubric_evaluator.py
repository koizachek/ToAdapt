from backend.evaluator.rubric_evaluator import RubricEvaluator


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
        ["analyse"],
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
