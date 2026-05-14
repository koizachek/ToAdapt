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
