
import pytest

from agents.core.planning_system import (
    Plan,
    PlanExecutor,
    PlanStep,
    Planner,
    StepType,
    Tool,
    ToolRegistry,
    ToolResult,
)


class AlwaysValidTool(Tool):
    name = "always_valid"
    description = "Succeeds with provided value"

    def __init__(self, value: str = "ok"):
        self.value = value

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, data={"value": self.value})


class ArgsValidatingTool(Tool):
    name = "args_validator"
    description = "Fails validation without required arg"

    def validate_args(self, args):
        if "needed" not in args:
            return "missing 'needed'"
        return None

    async def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, data={"value": kwargs.get("needed")})


@pytest.mark.asyncio
async def test_execute_plan_records_warnings_on_failure():
    tools = ToolRegistry()
    planner = Planner()
    executor = PlanExecutor(tools, planner, max_concurrent=1)

    tools.register(AlwaysValidTool())
    tools.register(ArgsValidatingTool())

    steps = [
        PlanStep(
            id="s1",
            name="Valid step",
            description="runs fine",
            step_type=StepType.TOOL,
            tool_name="always_valid",
        ),
        PlanStep(
            id="s2",
            name="Invalid args",
            description="will fail validation",
            step_type=StepType.TOOL,
            tool_name="args_validator",
            dependencies=["s1"],
            tool_args={},  # Missing required
            max_retries=1,
        ),
    ]
    plan = Plan(id="plan1", goal="test", steps=steps)

    result = await executor.execute_plan(plan)

    assert result["success"] is False or result["warnings"]  # warnings captured
    assert any("missing 'needed'" in w for w in result["warnings"])


@pytest.mark.asyncio
async def test_tool_validation_invoked_before_execute():
    tools = ToolRegistry()
    planner = Planner()
    executor = PlanExecutor(tools, planner)

    tools.register(ArgsValidatingTool())
    step = PlanStep(
        id="s1",
        name="Invalid args",
        description="fails validation",
        step_type=StepType.TOOL,
        tool_name="args_validator",
        tool_args={},
    )

    with pytest.raises(RuntimeError) as excinfo:
        await executor._execute_step(step)

    assert "Invalid arguments" in str(excinfo.value)


@pytest.mark.asyncio
async def test_successful_tool_sets_result():
    tools = ToolRegistry()
    planner = Planner()
    executor = PlanExecutor(tools, planner)
    tools.register(AlwaysValidTool(value="done"))

    step = PlanStep(
        id="s1",
        name="Run tool",
        description="should succeed",
        step_type=StepType.TOOL,
        tool_name="always_valid",
    )

    data = await executor._execute_step(step)

    assert data["value"] == "done"


@pytest.mark.asyncio
async def test_preconditions_block_until_effects_present():
    tools = ToolRegistry()
    planner = Planner()
    executor = PlanExecutor(tools, planner, max_concurrent=1)
    tools.register(AlwaysValidTool(value="ok"))

    # Two steps: second depends on effect of first
    steps = [
        PlanStep(
            id="s1",
            name="Seed state",
            description="adds effect",
            step_type=StepType.TOOL,
            tool_name="always_valid",
            effects=["ready"],
        ),
        PlanStep(
            id="s2",
            name="Needs state",
            description="requires ready",
            step_type=StepType.TOOL,
            tool_name="always_valid",
            preconditions=["ready"],
            dependencies=["s1"],
        ),
    ]
    plan = Plan(id="plan2", goal="stateful", steps=steps, context={"state": set()})

    result = await executor.execute_plan(plan)

    assert result["success"] is True
    assert "ready" in result["state"]


def test_priority_sorting_orders_ready_steps():
    Planner()
    high = PlanStep(
        id="a",
        name="High",
        description="",
        step_type=StepType.REASONING,
        priority=0.9,
    )
    low = PlanStep(
        id="b",
        name="Low",
        description="",
        step_type=StepType.REASONING,
        priority=0.1,
    )
    plan = Plan(id="p", goal="g", steps=[low, high])

    ready = plan.get_next_steps()

    assert ready[0].id == "a"
