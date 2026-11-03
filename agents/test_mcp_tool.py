#!/usr/bin/env python3
"""Test suite for MCPTool execution and content handling."""

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.tools.mcp_tool import MCPTool  # noqa: E402


class MockContentItem:
    def __init__(self, type_: str, text: str | None = None):
        self.type = type_
        if text is not None:
            self.text = text


class MockCallToolResult:
    def __init__(self, content: list | None = None):
        self.content = content if content is not None else []


def test_mcp_tool_multiple_text_blocks():
    """Verify that MCPTool preserves all text blocks in order."""

    async def run():
        response = MockCallToolResult(
            content=[
                MockContentItem(type_="text", text="Order 42: total $100."),
                MockContentItem(
                    type_="text",
                    text="Correction: order 42 was cancelled; amount due $0.",
                ),
            ]
        )
        connection = SimpleNamespace(call_tool=AsyncMock(return_value=response))
        tool = MCPTool(
            name="lookup_order",
            description="Order status",
            input_schema={"type": "object"},
            connection=connection,
        )

        actual = await tool.execute(order_id=42)
        expected = (
            "Order 42: total $100.\n\n"
            "Correction: order 42 was cancelled; amount due $0."
        )
        assert actual == expected

    asyncio.run(run())


def test_mcp_tool_single_text_block():
    """Verify backwards-compatibility with a single text block."""

    async def run():
        response = MockCallToolResult(
            content=[
                MockContentItem(type_="text", text="Single result line"),
            ]
        )
        connection = SimpleNamespace(call_tool=AsyncMock(return_value=response))
        tool = MCPTool(
            name="single_tool",
            description="Single tool",
            input_schema={"type": "object"},
            connection=connection,
        )

        actual = await tool.execute()
        assert actual == "Single result line"

    asyncio.run(run())


def test_mcp_tool_mixed_content_types():
    """Verify non-text blocks (e.g. image) are ignored while text blocks
    are preserved."""

    async def run():
        response = MockCallToolResult(
            content=[
                MockContentItem(type_="image"),
                MockContentItem(type_="text", text="First block"),
                MockContentItem(type_="audio"),
                MockContentItem(type_="text", text="Second block"),
            ]
        )
        connection = SimpleNamespace(call_tool=AsyncMock(return_value=response))
        tool = MCPTool(
            name="mixed_tool",
            description="Mixed tool",
            input_schema={"type": "object"},
            connection=connection,
        )

        actual = await tool.execute()
        assert actual == "First block\n\nSecond block"

    asyncio.run(run())


def test_mcp_tool_no_text_content():
    """Verify fallback message when response contains no text content."""

    async def run():
        response = MockCallToolResult(
            content=[
                MockContentItem(type_="image"),
            ]
        )
        connection = SimpleNamespace(call_tool=AsyncMock(return_value=response))
        tool = MCPTool(
            name="no_text_tool",
            description="No text tool",
            input_schema={"type": "object"},
            connection=connection,
        )

        actual = await tool.execute()
        assert actual == "No text content in tool response"

    asyncio.run(run())


def test_mcp_tool_empty_content():
    """Verify fallback message when response content list is empty."""

    async def run():
        response = MockCallToolResult(content=[])
        connection = SimpleNamespace(call_tool=AsyncMock(return_value=response))
        tool = MCPTool(
            name="empty_tool",
            description="Empty tool",
            input_schema={"type": "object"},
            connection=connection,
        )

        actual = await tool.execute()
        assert actual == "No text content in tool response"

    asyncio.run(run())


def test_mcp_tool_error_handling():
    """Verify exceptions during execution return a formatted error string."""

    async def run():
        connection = SimpleNamespace(
            call_tool=AsyncMock(side_effect=RuntimeError("connection dropped"))
        )
        tool = MCPTool(
            name="failing_tool",
            description="Failing tool",
            input_schema={"type": "object"},
            connection=connection,
        )

        actual = await tool.execute()
        assert actual == "Error executing failing_tool: connection dropped"

    asyncio.run(run())


if __name__ == "__main__":
    test_mcp_tool_multiple_text_blocks()
    test_mcp_tool_single_text_block()
    test_mcp_tool_mixed_content_types()
    test_mcp_tool_no_text_content()
    test_mcp_tool_empty_content()
    test_mcp_tool_error_handling()
    print("All MCPTool tests passed!")
