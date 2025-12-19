"""
Message rendering functionality for the Browser Use Demo.

This module handles all message rendering logic for the Streamlit interface,
separating presentation concerns from the main application logic.
"""

import base64
from typing import cast

import streamlit as st
from anthropic.types.beta import BetaContentBlockParam

from browser_use_demo.tools import ToolResult
from browser_use_demo.tools.coordinate_scaling import CoordinateScaler


class Sender:
    """Message sender types."""

    USER = "user"
    BOT = "assistant"
    TOOL = "tool"


class MessageRenderer:
    """Handles rendering of messages in the Streamlit chat interface."""

    def __init__(self, session_state):
        """Initialize the MessageRenderer with session state access.

        Args:
            session_state: Streamlit session state object for accessing configuration
        """
        self.session_state = session_state

    def _scale_browser_coordinates(self, input_dict: dict) -> dict:
        """Apply coordinate scaling to browser tool inputs for display.

        This ensures the displayed coordinates match what the browser tool will actually use.
        Uses the CoordinateScaler for consistent scaling across the codebase.

        Args:
            input_dict: The tool input dictionary

        Returns:
            Modified input dict with scaled coordinates
        """
        # Only process browser tool inputs with coordinates
        if not isinstance(input_dict, dict):
            return input_dict

        # Get browser tool dimensions if available
        browser_tool = getattr(self.session_state, 'browser_tool', None)
        if not browser_tool:
            return input_dict

        # Clone the input to avoid modifying the original
        import copy
        scaled_input = copy.deepcopy(input_dict)

        # Get viewport dimensions
        width = browser_tool.width
        height = browser_tool.height

        # Scale various coordinate fields using CoordinateScaler
        if 'coordinate' in scaled_input:
            scaled_input['coordinate'] = CoordinateScaler.scale_coordinate_list(
                scaled_input['coordinate'], width, height
            )

        if 'start_coordinate' in scaled_input:
            scaled_input['start_coordinate'] = CoordinateScaler.scale_coordinate_list(
                scaled_input['start_coordinate'], width, height
            )

        return scaled_input

    def render(self, sender: str, message: str | BetaContentBlockParam | ToolResult):
        """Render a message in the chat interface.

        Args:
            sender: The sender type (USER, BOT, or TOOL)
            message: The message content to render
        """
        # Early return for empty messages or hidden screenshots without content
        if self._should_skip_message(message):
            return

        with st.chat_message(sender):
            self._render_message_content(message)

    def _should_skip_message(self, message) -> bool:
        """Check if message should be skipped from rendering.

        Args:
            message: The message to check

        Returns:
            True if the message should be skipped, False otherwise
        """
        if not message:
            return True

        # Skip tool results that only have screenshots when screenshots are hidden
        is_tool_result = not isinstance(message, str | dict)
        if is_tool_result and self.session_state.hide_screenshots:
            return not hasattr(message, "error") and not hasattr(message, "output")

        return False

    def _render_message_content(self, message):
        """Render the actual message content based on its type.

        Args:
            message: The message content to render
        """
        # Define rendering strategies for different message types
        renderers = {
            "tool_result": self._render_tool_result,
            "dict": self._render_dict_message,
            "string": lambda msg: st.markdown(msg),
        }

        # Determine message type and render accordingly
        if not isinstance(message, str | dict):
            # It's a ToolResult object
            renderers["tool_result"](cast(ToolResult, message))
        elif isinstance(message, dict):
            renderers["dict"](message)
        else:
            renderers["string"](message)

    def _render_tool_result(self, tool_result: ToolResult):
        """Render a tool result with output, error, and optional image.

        Args:
            tool_result: The ToolResult object to render
        """
        if tool_result.output:
            # Check if this is a text extraction result with special markers
            if "__PAGE_EXTRACTED__" in tool_result.output or "__TEXT_EXTRACTED__" in tool_result.output:
                # Extract just the summary for display
                lines = tool_result.output.split("\n")
                summary_lines = []
                in_summary = False

                for line in lines:
                    if "__PAGE_EXTRACTED__" in line or "__TEXT_EXTRACTED__" in line:
                        in_summary = True
                        continue
                    if "__FULL_CONTENT__" in line:
                        break
                    if in_summary:
                        summary_lines.append(line)

                # Display only the summary
                if summary_lines:
                    st.markdown("\n".join(summary_lines))
            else:
                # Regular tool output
                st.markdown(tool_result.output)

        if tool_result.error:
            st.error(tool_result.error)
        if tool_result.base64_image and not self.session_state.hide_screenshots:
            st.image(base64.b64decode(tool_result.base64_image))

    def _render_dict_message(self, message: dict):
        """Render dictionary-based messages based on their type field.

        Args:
            message: Dictionary containing the message to render
        """
        message_type = message.get("type", "")

        # Dispatch table for different message types
        type_handlers = {
            "text": lambda: st.write(message["text"]),
            "tool_use": lambda: self._render_tool_use(message),
            "tool_result": lambda: self._render_stored_tool_result(message),
        }

        # Execute the appropriate handler or fall back to generic display
        handler = type_handlers.get(message_type, lambda: st.write(message))
        handler()

    def _render_tool_use(self, message: dict):
        """Render a tool use message with coordinate scaling for browser tools.

        Args:
            message: Dictionary containing tool use information
        """
        tool_name = message.get('name', 'unknown')
        tool_input = message.get('input', {})

        # Apply coordinate scaling for browser tool
        if tool_name == 'browser':
            tool_input = self._scale_browser_coordinates(tool_input)

        st.code(f"Tool Use: {tool_name}\nInput: {tool_input}")

    def _render_stored_tool_result(self, message: dict):
        """Render a tool result that was stored in session state.

        Args:
            message: Dictionary containing the tool_use_id reference
        """
        tool_id = message.get("tool_use_id")
        if tool_id and tool_id in self.session_state.tools:
            self._render_tool_result(self.session_state.tools[tool_id])

    def render_conversation_history(self, messages: list):
        """Render all messages in conversation history.

        This method processes a list of messages and renders each one
        according to its role and content type, eliminating deep nesting.

        Args:
            messages: List of message dictionaries from session state
        """
        for message in messages:
            self._render_message_by_role(message)

    def _render_message_by_role(self, message: dict):
        """Route message rendering based on role.

        Args:
            message: Message dictionary containing role and content
        """
        role_handlers = {
            "user": lambda m: self._render_user_content(m["content"]),
            "assistant": lambda m: self._render_assistant_content(m["content"]),
        }

        handler = role_handlers.get(message["role"])
        if handler:
            handler(message)

    def _render_user_content(self, content):
        """Render user message content.

        Handles both single items and lists of content blocks,
        skipping image blocks in conversation history.

        Args:
            content: User message content (string, dict, or list)
        """
        for item in self._normalize_content(content):
            # Skip image blocks in history
            if isinstance(item, dict) and item.get("type") == "image":
                continue

            # Extract text from dict blocks or use item directly
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_content = item.get("text", "")
                    self.render(Sender.USER, text_content)
                else:
                    # For other dict types, cast as BetaContentBlockParam
                    self.render(Sender.USER, cast(BetaContentBlockParam, item))
            else:
                self.render(Sender.USER, item)

    def _render_assistant_content(self, content):
        """Render assistant message content.

        Handles both single items and lists of content blocks,
        properly routing tool results to the TOOL sender.

        Args:
            content: Assistant message content (string, dict, or list)
        """
        for item in self._normalize_content(content):
            if isinstance(item, dict) and item.get("type") == "tool_result":
                # Handle tool results by fetching from session state
                tool_id = item.get("tool_use_id")
                if tool_id and tool_id in self.session_state.tools:
                    self.render(Sender.TOOL, self.session_state.tools[tool_id])
            elif isinstance(item, dict):
                # Cast dict items as BetaContentBlockParam
                self.render(Sender.BOT, cast(BetaContentBlockParam, item))
            else:
                # String or other types
                self.render(Sender.BOT, item)

    def _normalize_content(self, content):
        """Convert content to list for uniform processing.

        This eliminates duplicate code for handling list vs non-list content.

        Args:
            content: Content that may be a single item or list

        Returns:
            List of content items for processing
        """
        return content if isinstance(content, list) else [content]
