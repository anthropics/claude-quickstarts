"""Base tool definitions for the agent framework."""

from dataclasses import dataclass
from typing import Any


@dataclass
class Tool:
    """Base class for all agent tools."""

    name: str
    description: str
    input_schema: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert tool to Claude API format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    async def execute(self, **kwargs) -> str:
        """Execute the tool with provided parameters."""
        raise NotImplementedError(
            "Tool subclasses must implement execute method"
        )
