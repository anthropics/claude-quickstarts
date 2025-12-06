import pytest

from agents.core.planning_system import Plan, Planner, PlanExecutor, PlanStep, PlanStatus, StepType, ToolRegistry


class NoopTool:
    name = "noop"
    description = "noop"

    async def execute(self, **kwargs):
        from agents.core.planning_system import ToolResult
        return ToolResult(success=True, data={"ok": True})

    def validate_args(self, args):
        return None


@pytest.mark.asyncio
async def test_plan_blocks_when_unverified_required():
    tools = ToolRegistry()
    tools.register(NoopTool())
    planner = Planner()
    executor = PlanExecutor(tools, planner)

    steps = [
        PlanStep(
            id="s1",
            name="noop",
            description="",
            step_type=StepType.TOOL,
            tool_name="noop",
        )
    ]
    plan = Plan(id="p", goal="g", steps=steps, context={"require_verified": True, "verified": False})

    result = await executor.execute_plan(plan)

    assert result["success"] is False
    assert "unverified" in result["error"].lower()
    assert plan.status == PlanStatus.BLOCKED
