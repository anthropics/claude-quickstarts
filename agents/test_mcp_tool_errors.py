"""Check MCP failures through the agent's real tool-result conversion."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from anthropic.types import ToolUseBlock
from mcp.types import CallToolResult, TextContent

from agents.tools.mcp_tool import MCPTool
from agents.utils.tool_util import execute_tools


def make_tool(result=None, error=None):
    connection = SimpleNamespace(call_tool=AsyncMock(return_value=result, side_effect=error))
    tool = MCPTool("lookup", "Look up a record", {"type": "object"}, connection)
    return tool, connection


def call(identifier="call_1"):
    return ToolUseBlock(type="tool_use", id=identifier, name="lookup", input={"key": "x"})


@pytest.mark.parametrize("parallel", [False, True])
def test_mcp_error_result_sets_tool_result_error_flag(parallel):
    result = CallToolResult(
        is_error=True, content=[TextContent(type="text", text="Record not found")]
    )
    tool, connection = make_tool(result)

    responses = asyncio.run(execute_tools([call()], {"lookup": tool}, parallel=parallel))

    assert responses[0]["is_error"] is True
    assert "Record not found" in responses[0]["content"]
    assert responses[0]["tool_use_id"] == "call_1"
    connection.call_tool.assert_awaited_once_with("lookup", arguments={"key": "x"})


@pytest.mark.parametrize("parallel", [False, True])
def test_empty_mcp_error_result_is_still_an_error(parallel):
    tool, _ = make_tool(CallToolResult(is_error=True, content=[]))

    responses = asyncio.run(execute_tools([call()], {"lookup": tool}, parallel=parallel))

    assert responses[0]["is_error"] is True
    assert "No text content in tool response" in responses[0]["content"]


@pytest.mark.parametrize("parallel", [False, True])
def test_connection_failure_sets_tool_result_error_flag(parallel):
    tool, _ = make_tool(error=ConnectionError("connection dropped"))

    responses = asyncio.run(execute_tools([call()], {"lookup": tool}, parallel=parallel))

    assert responses[0]["is_error"] is True
    assert "connection dropped" in responses[0]["content"]


@pytest.mark.parametrize("parallel", [False, True])
def test_successful_error_text_is_not_classified_as_failure(parallel):
    tool, _ = make_tool(
        CallToolResult(content=[TextContent(type="text", text="Error rate: 0%")])
    )

    responses = asyncio.run(execute_tools([call()], {"lookup": tool}, parallel=parallel))

    assert responses == [
        {"type": "tool_result", "tool_use_id": "call_1", "content": "Error rate: 0%"}
    ]


@pytest.mark.parametrize("parallel", [False, True])
def test_mixed_results_keep_separate_error_states(parallel):
    tool, connection = make_tool()
    connection.call_tool.side_effect = [
        CallToolResult(is_error=True, content=[TextContent(type="text", text="Not found")]),
        CallToolResult(content=[TextContent(type="text", text="Found")]),
    ]

    responses = asyncio.run(
        execute_tools([call("bad"), call("good")], {"lookup": tool}, parallel=parallel)
    )

    assert responses[0]["tool_use_id"] == "bad"
    assert responses[0]["is_error"] is True
    assert responses[1] == {"type": "tool_result", "tool_use_id": "good", "content": "Found"}


def test_direct_connection_failure_preserves_cause():
    error = ConnectionError("connection dropped")
    tool, _ = make_tool(error=error)

    with pytest.raises(RuntimeError, match="connection dropped") as caught:
        asyncio.run(tool.execute(key="x"))

    assert caught.value.__cause__ is error


def test_empty_successful_result_keeps_existing_fallback():
    tool, _ = make_tool(CallToolResult(content=[]))

    assert asyncio.run(tool.execute()) == "No text content in tool response"


def test_cancellation_is_not_converted_to_a_tool_result():
    error = asyncio.CancelledError("cancelled")
    tool, _ = make_tool(error=error)

    with pytest.raises(asyncio.CancelledError) as caught:
        asyncio.run(execute_tools([call()], {"lookup": tool}))

    assert caught.value is error
