"""Tools that interface with MCP servers."""

from typing import Any
from .base import Tool
from ..utils.connections import MCPConnection


class MCPTool(Tool):
    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        connection: "MCPConnection",
    ):
        super().__init__(
            name=name, description=description, input_schema=input_schema
        )
        self.connection = connection

    async def execute(self, **kwargs) -> str:
        """Execute the MCP tool with the given input_schema.
        Note: Currently only supports text results from MCP tools."""
        try:
            result = await self.connection.call_tool(
                self.name, arguments=kwargs
            )

            if hasattr(result, "content") and result.content:
                for item in result.content:
                    if getattr(item, "type", None) == "text":
                        return item.text

            return "No text content in tool response"
        except Exception as e:
            return f"Error executing {self.name}: {e}"
