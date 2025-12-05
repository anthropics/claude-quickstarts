from agents.core.planning_system import ToolRegistry


class FastTool:
    name = "fast"
    description = "fast tool"

    async def execute(self, **kwargs):
        from agents.core.planning_system import ToolResult
        return ToolResult(success=True, data={"ok": True})


class SlowTool:
    name = "slow"
    description = "slow tool"

    async def execute(self, **kwargs):
        from agents.core.planning_system import ToolResult
        return ToolResult(success=True, data={"ok": True})


def test_select_best_prefers_higher_score():
    reg = ToolRegistry()
    reg.register(FastTool())
    reg.register(SlowTool())

    # Simulate stats
    reg.record_usage("fast", success=True, execution_time_ms=100)
    reg.record_usage("fast", success=True, execution_time_ms=120)
    reg.record_usage("slow", success=True, execution_time_ms=5000)

    best = reg.best_tool(["fast", "slow"])
    assert best == "fast"
