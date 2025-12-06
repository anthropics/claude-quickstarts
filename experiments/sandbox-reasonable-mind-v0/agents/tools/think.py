"""Think tool for internal reasoning."""

from .base import Tool


class ThinkTool(Tool):
    """Tool for internal reasoning without executing external actions."""

    def __init__(self):
        super().__init__(
            name="think",
            description=(
                "Use the tool to think about something. It will not obtain "
                "new information or change the database, but just append the "
                "thought to the log. Use it when complex reasoning or some "
                "cache memory is needed."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "thought": {
                        "type": "string",
                        "description": "A thought to think about.",
                    }
                },
                "required": ["thought"],
            },
        )

    async def execute(self, thought: str) -> str:
        """Simply returns the thought back to the model."""
        return "Thinking complete!"
