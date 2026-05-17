from backend.agents.orchestrator import guardrail_check


def test_guardrail_blocks_direct_use_case_recommendation():
    ok, reason = guardrail_check(
        "Der Website-Chatbot ist die beste Wahl, weil er schneller umsetzbar ist.",
        2,
    )
    assert ok is False
    assert reason == "direct_recommendation_or_template"


def test_guardrail_blocks_case_speculation():
    ok, reason = guardrail_check(
        "FINMA-konformes Swiss Hosting auf Azure Switzerland waere hier zentral.",
        3,
    )
    assert ok is False
    assert reason == "case_speculation_outside_context"


def test_guardrail_blocks_slang_and_emoji():
    ok, reason = guardrail_check(
        "Haha, du packst das 🔥",
        1,
    )
    assert ok is False
    assert reason in {"style_contains_slang", "style_contains_emoji"}
