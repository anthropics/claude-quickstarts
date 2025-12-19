from typing import Any

from anthropic.types.beta import BetaToolUnionParam

from .base import BaseAnthropicTool


class ToolCollection:
    """Collection of tools for browser automation."""

    def __init__(self, *tools: BaseAnthropicTool):
        self.tools = tools
        self.tool_map = {tool.name: tool for tool in tools}

    def to_params(self) -> list[BetaToolUnionParam]:
        """Convert all tools to API parameters."""
        return [tool.to_params() for tool in self.tools]
