from prompts import get_builder_prompt, get_evaluator_prompt, get_planner_prompt


def test_phase_prompts_load() -> None:
    planner = get_planner_prompt()
    builder = get_builder_prompt()
    evaluator = get_evaluator_prompt()

    assert "ROLE" in planner
    assert "ROLE" in builder
    assert "ROLE" in evaluator

    assert "sprint contract" in builder.lower()
    assert "few-shot" in evaluator.lower()
    assert "ai" in planner.lower()
