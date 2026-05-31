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
