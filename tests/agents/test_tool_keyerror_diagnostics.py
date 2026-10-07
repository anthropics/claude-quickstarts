import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from utils.tool_util import _execute_single_tool


def test_execution_keyerror_is_not_reported_as_missing_tool():
    tool = SimpleNamespace(execute=AsyncMock(side_effect=KeyError("required_field")))
    call = SimpleNamespace(id="call_1", name="example", input={})
    result = asyncio.run(_execute_single_tool(call, {"example": tool}))
    assert result["is_error"] is True
    assert result["content"] == "Error executing tool: 'required_field'"
    assert result["tool_use_id"] == "call_1"


def test_missing_tool_keeps_lookup_error():
    call = SimpleNamespace(id="call_1", name="missing", input={})
    result = asyncio.run(_execute_single_tool(call, {}))
    assert result["content"] == "Tool 'missing' not found"
    assert result["is_error"] is True


def test_successful_tool_result():
    tool = SimpleNamespace(execute=AsyncMock(return_value="done"))
    call = SimpleNamespace(id="call_1", name="example", input={"value": 1})
    result = asyncio.run(_execute_single_tool(call, {"example": tool}))
    assert result == {"type": "tool_result", "tool_use_id": "call_1", "content": "done"}
    tool.execute.assert_awaited_once_with(value=1)
