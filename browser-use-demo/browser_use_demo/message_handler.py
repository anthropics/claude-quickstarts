"""
Message handling abstractions for proper API response processing.

This module provides clean abstractions for processing API responses and building
messages that preserve both text explanations and tool uses together, matching
the Chrome extension's behavior.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional, cast

from anthropic.types.beta import (
    BetaContentBlockParam,
    BetaImageBlockParam,
    BetaMessageParam,
    BetaTextBlockParam,
    BetaToolResultBlockParam,
)

from .tools import ToolCollection, ToolResult


@dataclass
class ProcessedResponse:
    """Container for processed API response data."""

    assistant_content: list[BetaContentBlockParam]
    tool_uses: list[dict[str, Any]]
    has_text: bool
    has_tools: bool


class ResponseProcessor:
    """
    Handles API response processing with proper message preservation.

    This class ensures that text explanations are preserved alongside tool uses,
    matching the behavior of the Chrome extension.
    """

    def process_response(self, response) -> ProcessedResponse:
        """
        Process an API response into a structured format.

        Args:
            response: The API response from Anthropic

        Returns:
            ProcessedResponse containing all content blocks and metadata
        """
        assistant_content = []
        tool_uses = []
        has_text = False
        has_tools = False

        for content_block in response.content:
            if content_block.type == "text":
                has_text = True
                assistant_content.append({
                    "type": "text",
                    "text": content_block.text
                })
            elif content_block.type == "tool_use":
                has_tools = True
                tool_use_dict = {
                    "type": "tool_use",
                    "id": content_block.id,
                    "name": content_block.name,
                    "input": content_block.input
                }
                assistant_content.append(tool_use_dict)
                tool_uses.append(tool_use_dict)

        return ProcessedResponse(
            assistant_content=assistant_content,
            tool_uses=tool_uses,
            has_text=has_text,
            has_tools=has_tools
        )

    async def execute_tools(
        self,
        tool_uses: list[dict[str, Any]],
        tool_collection: ToolCollection,
        tool_output_callback: Optional[Callable[[ToolResult, str], None]] = None
    ) -> list[BetaToolResultBlockParam]:
        """
        Execute tools and collect results.

        Args:
            tool_uses: List of tool use blocks to execute
            tool_collection: The tool collection for execution
            tool_output_callback: Optional callback for tool results

        Returns:
            List of tool result blocks
        """
        tool_results = []

        for tool_use in tool_uses:
            tool_id = tool_use["id"]
            tool_name = tool_use["name"]
            tool_input = tool_use["input"]

            try:
                tool = tool_collection.tool_map.get(tool_name)
                if not tool:
                    raise ValueError(f"Unknown tool: {tool_name}")

                result = await tool(**tool_input)

                if tool_output_callback:
                    tool_output_callback(result, tool_id)

                tool_result = self._build_tool_result(result, tool_id)
                tool_results.append(tool_result)

            except Exception as e:
                error_result = BetaToolResultBlockParam(
                    type="tool_result",
                    tool_use_id=tool_id,
                    is_error=True,
                    content=[{"type": "text", "text": str(e)}]
                )
                tool_results.append(error_result)

                if tool_output_callback:
                    error_tool_result = ToolResult(error=str(e))
                    tool_output_callback(error_tool_result, tool_id)

        return tool_results

    def _build_tool_result(
        self,
        result: ToolResult,
        tool_use_id: str
    ) -> BetaToolResultBlockParam:
        """
        Build a tool result block from a ToolResult.

        Args:
            result: The tool execution result
            tool_use_id: The ID of the tool use

        Returns:
            A properly formatted tool result block
        """
        tool_result = BetaToolResultBlockParam(
            type="tool_result",
            tool_use_id=tool_use_id,
            content=[]
        )

        content_list = cast(list[BetaTextBlockParam | BetaImageBlockParam], tool_result.get("content", []))

        if result.output:
            output_text = result.output
            if "__PAGE_EXTRACTED__" in output_text or "__TEXT_EXTRACTED__" in output_text:
                if "__FULL_CONTENT__" in output_text:
                    marker_pos = output_text.index("__FULL_CONTENT__")
                    output_text = output_text[marker_pos + len("__FULL_CONTENT__") + 1:]

            content_list.append({
                "type": "text",
                "text": output_text
            })

        if result.base64_image:
            content_list.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": result.base64_image,
                }
            })

        if result.error:
            tool_result["is_error"] = True
            content_list.append({
                "type": "text",
                "text": f"Error: {result.error}"
            })

        return tool_result


class MessageBuilder:
    """
    Builds properly structured messages for the API.

    This class ensures messages are constructed in a way that preserves
    all content, matching the Chrome extension's behavior.
    """

    def add_assistant_message(
        self,
        messages: list[BetaMessageParam],
        content: list[BetaContentBlockParam]
    ) -> None:
        """
        Add a complete assistant message with all content blocks.

        Args:
            messages: The message list to append to
            content: The content blocks for the assistant message
        """
        if content:  # Only add if there's content
            messages.append({
                "role": "assistant",
                "content": content
            })

    def add_tool_results(
        self,
        messages: list[BetaMessageParam],
        tool_results: list[BetaToolResultBlockParam]
    ) -> None:
        """
        Add tool results as a user message.

        Args:
            messages: The message list to append to
            tool_results: The tool result blocks to add
        """
        if tool_results:  # Only add if there are results
            messages.append({
                "role": "user",
                "content": tool_results
            })

    def ensure_message_integrity(
        self,
        messages: list[BetaMessageParam]
    ) -> bool:
        """
        Validate that messages maintain proper structure.

        Args:
            messages: The message list to validate

        Returns:
            True if messages are properly structured, False otherwise
        """
        if not messages:
            return True

        for message in messages:
            role = message.get("role")
            if not role:
                return False

            if "content" not in message:
                return False

            content = message["content"]
            if isinstance(content, list) and len(content) == 0:
                return False

        return True

    def extract_text_from_message(
        self,
        message: BetaMessageParam
    ) -> Optional[str]:
        """
        Extract text content from a message.

        Args:
            message: The message to extract text from

        Returns:
            The extracted text or None if no text content
        """
        if message.get("role") != "assistant":
            return None

        content = message.get("content", [])
        if isinstance(content, str):
            return content

        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        return " ".join(text_parts) if text_parts else None
