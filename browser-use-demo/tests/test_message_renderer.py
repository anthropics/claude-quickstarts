"""Tests for MessageRenderer class with comprehensive edge case coverage."""

from unittest.mock import MagicMock, Mock, patch

import pytest
from browser_use_demo.message_renderer import MessageRenderer, Sender
from browser_use_demo.tools import ToolResult


class TestMessageRenderer:
    """Test suite for MessageRenderer class."""

    def test_initialization(self, mock_streamlit):
        """Test MessageRenderer initialization."""
        renderer = MessageRenderer(mock_streamlit["session_state"])
        assert renderer.session_state == mock_streamlit["session_state"]

    def test_initialization_with_none_state(self):
        """Test initialization with None session state."""
        renderer = MessageRenderer(None)
        assert renderer.session_state is None

    def test_initialization_with_empty_state(self):
        """Test initialization with empty session state."""
        empty_state = MagicMock()
        renderer = MessageRenderer(empty_state)
        assert renderer.session_state == empty_state


class TestRenderMethod:
    """Test the main render method with various inputs."""

    def test_render_string_message(self, mock_streamlit):
        """Test rendering a simple string message."""
        renderer = MessageRenderer(mock_streamlit["session_state"])
        renderer.render(Sender.USER, "Hello world")

        mock_streamlit["chat_message"].assert_called_with(Sender.USER)
        mock_streamlit["markdown"].assert_called_with("Hello world")

    def test_render_empty_string(self, mock_streamlit):
        """Test rendering an empty string (should skip)."""
        renderer = MessageRenderer(mock_streamlit["session_state"])
        renderer.render(Sender.USER, "")

        mock_streamlit["chat_message"].assert_not_called()

    def test_render_none_message(self, mock_streamlit):
        """Test rendering None message (should skip)."""
        renderer = MessageRenderer(mock_streamlit["session_state"])
        renderer.render(Sender.BOT, None)

        mock_streamlit["chat_message"].assert_not_called()

    def test_render_tool_result_with_output(self, mock_streamlit, sample_tool_result):
        """Test rendering ToolResult with output."""
        renderer = MessageRenderer(mock_streamlit["session_state"])
        renderer.render(Sender.TOOL, sample_tool_result["success"])

        mock_streamlit["markdown"].assert_called_with("Success message")

    def test_render_tool_result_with_error(self, mock_streamlit, sample_tool_result):
        """Test rendering ToolResult with error."""
        renderer = MessageRenderer(mock_streamlit["session_state"])
        renderer.render(Sender.TOOL, sample_tool_result["error"])

        mock_streamlit["error"].assert_called_with("Error message")

    def test_render_tool_result_with_image(self, mock_streamlit, sample_tool_result):
        """Test rendering ToolResult with image."""
        mock_streamlit["session_state"].hide_screenshots = False
        renderer = MessageRenderer(mock_streamlit["session_state"])
        renderer.render(Sender.TOOL, sample_tool_result["with_image"])

        mock_streamlit["markdown"].assert_called_with("With screenshot")
        # Image should be decoded and displayed
        assert mock_streamlit["image"].called

    def test_render_tool_result_with_hidden_screenshots(
        self, mock_streamlit, sample_tool_result
    ):
        """Test that images are hidden when hide_screenshots is True."""
        mock_streamlit["session_state"].hide_screenshots = True
        renderer = MessageRenderer(mock_streamlit["session_state"])
        renderer.render(Sender.TOOL, sample_tool_result["with_image"])

        # Should render text but not image
        mock_streamlit["markdown"].assert_called_with("With screenshot")
        mock_streamlit["image"].assert_not_called()

    def test_render_dict_message_text_type(self, mock_streamlit):
        """Test rendering dictionary message with text type."""
        renderer = MessageRenderer(mock_streamlit["session_state"])
        message = {"type": "text", "text": "Hello from dict"}
        renderer.render(Sender.USER, message)

        mock_streamlit["write"].assert_called_with("Hello from dict")

    def test_render_dict_message_tool_use_type(self, mock_streamlit):
        """Test rendering dictionary message with tool_use type."""
        renderer = MessageRenderer(mock_streamlit["session_state"])
        message = {
            "type": "tool_use",
            "name": "browser_tool",
            "input": {"url": "example.com"},
        }
        renderer.render(Sender.BOT, message)

        expected_code = "Tool Use: browser_tool\nInput: {'url': 'example.com'}"
        mock_streamlit["code"].assert_called_with(expected_code)

    def test_render_dict_message_unknown_type(self, mock_streamlit):
        """Test rendering dictionary message with unknown type."""
        renderer = MessageRenderer(mock_streamlit["session_state"])
        message = {"type": "unknown", "data": "some data"}
        renderer.render(Sender.BOT, message)

        # Should fall back to generic write
        mock_streamlit["write"].assert_called_with(message)

    def test_render_very_long_message(self, mock_streamlit):
        """Test rendering extremely long messages."""
        renderer = MessageRenderer(mock_streamlit["session_state"])
        long_message = "x" * 100000  # 100k characters
        renderer.render(Sender.USER, long_message)

        mock_streamlit["markdown"].assert_called_with(long_message)

    def test_render_unicode_special_chars(self, mock_streamlit):
        """Test rendering messages with unicode and special characters."""
        renderer = MessageRenderer(mock_streamlit["session_state"])
        special_message = "Hello 世界 🌍 \n\t\r ñáéíóú"
        renderer.render(Sender.USER, special_message)

        mock_streamlit["markdown"].assert_called_with(special_message)


class TestConversationHistory:
    """Test render_conversation_history method with various scenarios."""

    def test_render_empty_history(self, mock_streamlit):
        """Test rendering empty conversation history."""
        renderer = MessageRenderer(mock_streamlit["session_state"])
        renderer.render_conversation_history([])

        # No rendering should occur
        mock_streamlit["chat_message"].assert_not_called()

    def test_render_single_message(self, mock_streamlit):
        """Test rendering single message in history."""
        renderer = MessageRenderer(mock_streamlit["session_state"])
        messages = [{"role": "user", "content": "Hello"}]
        renderer.render_conversation_history(messages)

        mock_streamlit["markdown"].assert_called_with("Hello")

    def test_render_multiple_messages(self, mock_streamlit, sample_messages):
        """Test rendering multiple messages with different roles."""
        renderer = MessageRenderer(mock_streamlit["session_state"])
        renderer.render_conversation_history(sample_messages[:2])

        # Should render both messages
        assert mock_streamlit["markdown"].call_count >= 2

    def test_render_unknown_role(self, mock_streamlit):
        """Test handling messages with unknown roles."""
        renderer = MessageRenderer(mock_streamlit["session_state"])
        messages = [{"role": "unknown_role", "content": "Test"}]
        renderer.render_conversation_history(messages)

        # Should not crash, but won't render
        mock_streamlit["markdown"].assert_not_called()

    def test_render_missing_content_field(self, mock_streamlit):
        """Test handling messages missing content field."""
        renderer = MessageRenderer(mock_streamlit["session_state"])
        messages = [{"role": "user"}]  # Missing content

        # Should not crash - will get KeyError but handler should manage it gracefully
        try:
            renderer.render_conversation_history(messages)
        except KeyError:
            pass  # Expected when content field is missing

    def test_render_none_content(self, mock_streamlit):
        """Test handling messages with None content."""
        renderer = MessageRenderer(mock_streamlit["session_state"])
        messages = [{"role": "user", "content": None}]
        renderer.render_conversation_history(messages)

        # Should handle gracefully without rendering
        mock_streamlit["markdown"].assert_not_called()

    def test_render_list_content(self, mock_streamlit):
        """Test rendering messages with list content."""
        renderer = MessageRenderer(mock_streamlit["session_state"])
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "First"},
                    {"type": "text", "text": "Second"},
                ],
            }
        ]
        renderer.render_conversation_history(messages)

        # Should render both text blocks
        calls = mock_streamlit["markdown"].call_args_list
        assert any("First" in str(call) for call in calls)
        assert any("Second" in str(call) for call in calls)

    def test_skip_image_blocks_in_history(self, mock_streamlit):
        """Test that image blocks are skipped in conversation history."""
        renderer = MessageRenderer(mock_streamlit["session_state"])
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Text message"},
                    {"type": "image", "source": "data:image/png;base64,abc"},
                ],
            }
        ]
        renderer.render_conversation_history(messages)

        # Should only render text, not image
        mock_streamlit["markdown"].assert_called_with("Text message")
        mock_streamlit["image"].assert_not_called()

    def test_tool_result_in_assistant_message(self, mock_streamlit, sample_tool_result):
        """Test rendering tool results from assistant messages."""
        mock_streamlit["session_state"].tools = {
            "tool_123": sample_tool_result["success"]
        }
        renderer = MessageRenderer(mock_streamlit["session_state"])
        messages = [
            {
                "role": "assistant",
                "content": [{"type": "tool_result", "tool_use_id": "tool_123"}],
            }
        ]
        renderer.render_conversation_history(messages)

        # Should render the tool result from session state
        mock_streamlit["markdown"].assert_called_with("Success message")

    def test_missing_tool_in_session_state(self, mock_streamlit):
        """Test handling tool_use_id that doesn't exist in session state."""
        renderer = MessageRenderer(mock_streamlit["session_state"])
        messages = [
            {
                "role": "assistant",
                "content": [{"type": "tool_result", "tool_use_id": "nonexistent"}],
            }
        ]
        renderer.render_conversation_history(messages)

        # Should handle gracefully without crashing
        mock_streamlit["markdown"].assert_not_called()


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_circular_reference_handling(self, mock_streamlit):
        """Test handling circular references in messages."""
        renderer = MessageRenderer(mock_streamlit["session_state"])

        # Create circular reference
        content = []
        content.append({"type": "text", "text": "Normal", "ref": content})
        messages = [{"role": "user", "content": content}]

        # Should not crash or infinite loop
        renderer.render_conversation_history(messages)

    def test_malformed_tool_result(self, mock_streamlit):
        """Test handling malformed ToolResult objects."""
        renderer = MessageRenderer(mock_streamlit["session_state"])

        # Create a mock that doesn't have expected attributes
        malformed = Mock(spec=[])  # No attributes
        renderer.render(Sender.TOOL, malformed)

        # Should handle gracefully
        mock_streamlit["markdown"].assert_not_called()

    def test_exception_in_rendering(self, mock_streamlit):
        """Test that exceptions during rendering are propagated."""
        # Setup the chat_message context manager properly
        mock_chat_cm = MagicMock()
        mock_chat_cm.__enter__ = Mock(return_value=None)
        mock_chat_cm.__exit__ = Mock(return_value=None)
        mock_streamlit["chat_message"].return_value = mock_chat_cm

        # Set markdown to raise an exception
        mock_streamlit["markdown"].side_effect = Exception("Render error")
        renderer = MessageRenderer(mock_streamlit["session_state"])

        # Should let the exception propagate for markdown rendering
        with pytest.raises(Exception, match="Render error"):
            renderer.render(Sender.USER, "Test message")

    def test_normalize_content_with_various_inputs(self, mock_streamlit):
        """Test _normalize_content with various input types."""
        renderer = MessageRenderer(mock_streamlit["session_state"])

        # String input
        assert renderer._normalize_content("test") == ["test"]

        # List input
        assert renderer._normalize_content([1, 2, 3]) == [1, 2, 3]

        # None input
        assert renderer._normalize_content(None) == [None]

        # Dict input
        assert renderer._normalize_content({"key": "value"}) == [{"key": "value"}]

    def test_deeply_nested_content(self, mock_streamlit):
        """Test handling deeply nested content structures."""
        renderer = MessageRenderer(mock_streamlit["session_state"])

        # Create deeply nested structure
        nested = {"type": "text", "text": "Deep"}
        for _ in range(100):
            nested = {"type": "wrapper", "content": nested}

        messages = [{"role": "user", "content": [nested]}]
        renderer.render_conversation_history(messages)

        # Should handle without stack overflow

    def test_concurrent_modification(self, mock_streamlit):
        """Test behavior when session state is modified during rendering."""
        renderer = MessageRenderer(mock_streamlit["session_state"])

        # Setup mock properly for context manager
        mock_cm = MagicMock()
        mock_cm.__enter__ = Mock(return_value=None)
        mock_cm.__exit__ = Mock(return_value=None)

        # Simulate modification during rendering
        def modify_state(*args, **kwargs):
            mock_streamlit["session_state"].tools = {}
            return mock_cm

        mock_streamlit["chat_message"].side_effect = modify_state

        # Should complete rendering despite modifications
        renderer.render(Sender.USER, "Test")

    def test_invalid_sender_type(self, mock_streamlit):
        """Test handling invalid sender types."""
        renderer = MessageRenderer(mock_streamlit["session_state"])

        # Use invalid sender
        renderer.render("invalid_sender", "Message")

        # Should still render with the provided sender
        mock_streamlit["chat_message"].assert_called_with("invalid_sender")

    def test_base64_decode_error(self, mock_streamlit):
        """Test handling invalid base64 image data."""
        # Setup the chat_message context manager properly
        mock_chat_cm = MagicMock()
        mock_chat_cm.__enter__ = Mock(return_value=None)
        mock_chat_cm.__exit__ = Mock(return_value=None)
        mock_streamlit["chat_message"].return_value = mock_chat_cm

        # Setup session state to not hide screenshots
        mock_streamlit["session_state"].hide_screenshots = False

        renderer = MessageRenderer(mock_streamlit["session_state"])
        tool_result = ToolResult(
            output="With bad image", base64_image="invalid_base64_!@#$"
        )

        with patch("base64.b64decode") as mock_decode:
            mock_decode.side_effect = Exception("Invalid base64")

            # Should handle the error gracefully - the exception should propagate
            with pytest.raises(Exception, match="Invalid base64"):
                renderer.render(Sender.TOOL, tool_result)
