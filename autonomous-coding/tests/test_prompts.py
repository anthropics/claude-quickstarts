from prompts import get_builder_prompt, get_evaluator_prompt, get_planner_prompt


def test_phase_prompts_load() -> None:
    assert "ROLE" in get_planner_prompt()
    assert "ROLE" in get_builder_prompt()
    assert "ROLE" in get_evaluator_prompt()
