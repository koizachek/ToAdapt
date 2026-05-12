from backend.cases.manager import case_manager
from backend.evaluator.rubric_loader import load_question_rubric


def test_load_question_rubric_for_case_questions():
    case = case_manager.get("alpes-bank-genai-001")
    assert case is not None

    rubrics = {
        question.question_id: load_question_rubric(question)
        for question in case.questions
    }

    assert rubrics["q1"] is not None
    assert rubrics["q2"] is not None
    assert rubrics["q3"] is not None
    assert rubrics["q4"] is not None

    assert rubrics["q1"].required_canvas_blocks[0].block == "customer_relationships"
    assert rubrics["q2"].required_canvas_blocks[1].block == "key_resources"
    assert rubrics["q3"].required_canvas_blocks[0].block == "key_partners"
    assert rubrics["q4"].required_canvas_blocks[-1].block == "cost_structure"
