from prompts import get_builder_prompt, get_evaluator_prompt, get_initializer_prompt, get_planner_prompt


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


def test_test_count_placeholders_are_rendered() -> None:
    initializer = get_initializer_prompt(target_test_count=321)
    planner = get_planner_prompt(target_test_count=321)

    assert "{{TARGET_TEST_COUNT}}" not in initializer
    assert "{{TARGET_TEST_COUNT}}" not in planner
    assert "321" in initializer
    assert "321" in planner
