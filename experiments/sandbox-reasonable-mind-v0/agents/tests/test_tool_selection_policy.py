from agents.core.planning_system import ToolRegistry


class DummyTool:
    name = "dummy"
    description = "d"

    async def execute(self, **kwargs):
        pass

    def validate_args(self, args):
        return None


def test_best_tool_prefers_success_rate():
    registry = ToolRegistry()
    t1 = DummyTool()
    t1.name = "a"
    t2 = DummyTool()
    t2.name = "b"
    registry.register(t1)
    registry.register(t2)
    # tool a: 2/2
    registry.record_usage("a", True, 10)
    registry.record_usage("a", True, 10)
    # tool b: 1/3
    registry.record_usage("b", True, 10)
    registry.record_usage("b", False, 10)
    registry.record_usage("b", False, 10)

    best = registry.best_tool()

    assert best == "a"
