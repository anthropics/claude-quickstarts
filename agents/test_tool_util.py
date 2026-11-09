import asyncio
from types import SimpleNamespace

import pytest

from agents.utils.tool_util import execute_tools


@pytest.mark.parametrize("parallel", [False, True])
def test_tool_lookup_and_execution_errors(parallel):
    class LookupTool:
        async def execute(self, key):
            return {"known": "value"}[key]

    calls = [
        SimpleNamespace(id="success", name="lookup", input={"key": "known"}),
        SimpleNamespace(id="execution-error", name="lookup", input={"key": "missing"}),
        SimpleNamespace(id="unknown-tool", name="unknown", input={}),
    ]
    results = asyncio.run(execute_tools(calls, {"lookup": LookupTool()}, parallel))

    assert results == [
        {"type": "tool_result", "tool_use_id": "success", "content": "value"},
        {
            "type": "tool_result",
            "tool_use_id": "execution-error",
            "content": "Error executing tool: 'missing'",
            "is_error": True,
        },
        {
            "type": "tool_result",
            "tool_use_id": "unknown-tool",
            "content": "Tool 'unknown' not found",
            "is_error": True,
        },
    ]
