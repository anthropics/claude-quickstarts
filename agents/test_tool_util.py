import asyncio
from types import SimpleNamespace

import pytest

from agents.utils.tool_util import execute_tools


@pytest.mark.parametrize("parallel", [False, True])
@pytest.mark.parametrize(
    "key, expected_error",
    [
        ("missing", "KeyError: 'missing'"),
        ("invalid", "ValueError: invalid key"),
    ],
)
def test_tool_lookup_and_execution_errors(parallel, key, expected_error):
    class LookupTool:
        async def execute(self, key):
            if key == "invalid":
                raise ValueError("invalid key")
            return {"known": "value"}[key]

    calls = [
        SimpleNamespace(id="success", name="lookup", input={"key": "known"}),
        SimpleNamespace(id="execution-error", name="lookup", input={"key": key}),
        SimpleNamespace(id="unknown-tool", name="unknown", input={}),
    ]
    results = asyncio.run(execute_tools(calls, {"lookup": LookupTool()}, parallel))

    assert results == [
        {"type": "tool_result", "tool_use_id": "success", "content": "value"},
        {
            "type": "tool_result",
            "tool_use_id": "execution-error",
            "content": f"Error executing tool: {expected_error}",
            "is_error": True,
        },
        {
            "type": "tool_result",
            "tool_use_id": "unknown-tool",
            "content": "Tool 'unknown' not found",
            "is_error": True,
        },
    ]
