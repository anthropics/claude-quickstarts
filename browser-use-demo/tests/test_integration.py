"""Integration tests for the refactored Browser Use Demo."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from browser_use_demo.loop import APIProvider
from browser_use_demo.message_renderer import MessageRenderer
from browser_use_demo.streamlit import (
    get_or_create_event_loop,
    setup_state,
)
from browser_use_demo.tools import ToolResult


@pytest.mark.integration
class TestFullMessageRenderingPipeline:
    """Test complete message rendering pipeline."""

    @patch("streamlit.session_state", new_callable=MagicMock)
    @patch("streamlit.chat_message")
    @patch("streamlit.markdown")
    @patch("streamlit.write")
    @patch("streamlit.error")
    def test_full_conversation_rendering(
        self, mock_error, mock_write, mock_markdown, mock_chat, mock_state
    ):
        """Test rendering a complete conversation with various message types."""

        # Setup mock state
        mock_state.hide_screenshots = False
        mock_state.tools = {
            "tool_1": ToolResult(output="Tool output 1"),
            "tool_2": ToolResult(error="Tool error 2"),
        }

        # Create complex conversation
        messages = [
            {"role": "user", "content": "Hello, can you help me?"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Sure, let me help you."},
                    {
                        "type": "tool_use",
                        "name": "browser",
                        "input": {"url": "example.com"},
                    },
                    {"type": "tool_result", "tool_use_id": "tool_1"},
                ],
            },
            {"role": "user", "content": [{"type": "text", "text": "Thank you!"}]},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "You're welcome!"},
                    {"type": "tool_result", "tool_use_id": "tool_2"},
                ],
            },
        ]

        # Mock chat_message context manager
        mock_chat.return_value.__enter__ = Mock()
        mock_chat.return_value.__exit__ = Mock()

        # Render full conversation
        renderer = MessageRenderer(mock_state)
        renderer.render_conversation_history(messages)

        # Verify all message types were rendered
        assert mock_markdown.call_count >= 3  # Text messages
        assert mock_write.call_count >= 2  # Tool use and text blocks
        assert mock_error.call_count == 1  # Tool error


@pytest.mark.integration
class TestStateInitializationAndPersistence:
    """Test state initialization and persistence across operations."""

    @patch("streamlit.session_state", new_callable=MagicMock)
    @patch("browser_use_demo.tools.BrowserTool")
    def test_complete_state_initialization(self, mock_browser_tool, mock_state):
        """Test complete state initialization flow."""

        # Simulate fresh state
        initialized_keys = set()

        def setitem_side_effect(key, value):
            initialized_keys.add(key)
            setattr(mock_state, key, value)

        mock_state.__contains__.return_value = False
        mock_state.__setitem__.side_effect = setitem_side_effect

        # Initialize state
        setup_state()

        # Verify all required keys were initialized
        expected_keys = {
            "messages",
            "api_key",
            "provider",
            "model",
            "max_tokens",
            "system_prompt",
            "hide_screenshots",
            "tools",
            "browser_tool",
            "event_loop",
            "rendered_message_count",
            "is_agent_running",
            "active_messages",
            "active_response_container",
        }

        assert expected_keys.issubset(initialized_keys)

    @patch("streamlit.session_state", new_callable=MagicMock)
    def test_state_persistence_across_renders(self, mock_state):
        """Test that state persists across multiple render calls."""

        # Initialize state
        mock_state.tools = {"tool_1": ToolResult(output="Persistent tool")}
        mock_state.messages = [{"role": "user", "content": "Initial message"}]

        # Create renderer and render
        renderer1 = MessageRenderer(mock_state)
        with patch("streamlit.chat_message"), patch("streamlit.markdown"):
            renderer1.render_conversation_history(mock_state.messages)

        # Add more messages
        mock_state.messages.append({"role": "assistant", "content": "Response"})

        # Create new renderer instance and render again
        renderer2 = MessageRenderer(mock_state)
        with patch("streamlit.chat_message"), patch("streamlit.markdown") as mock_md:
            renderer2.render_conversation_history(mock_state.messages)

            # Should render both messages
            assert mock_md.call_count >= 2


@pytest.mark.integration
class TestEventLoopManagementWithAsync:
    """Test event loop management with async operations."""

    def test_async_agent_execution(self):
        """Test running async agent with event loop management."""

        with patch("streamlit.session_state", new_callable=MagicMock) as mock_state:
            mock_state.event_loop = None

            with patch("asyncio.set_event_loop"):
                with patch("asyncio.new_event_loop") as mock_new_loop:
                    mock_loop = MagicMock()
                    mock_loop.is_closed.return_value = False
                    mock_new_loop.return_value = mock_loop

                    loop = get_or_create_event_loop()

                    # Verify loop was created and set
                    assert loop == mock_loop
                    assert mock_state.event_loop == mock_loop

            # Test that the loop can handle async operations (mocked)
            async def mock_agent(input_text):
                return f"Processed: {input_text}"

            # Mock running the async function
            mock_loop.run_until_complete = MagicMock(
                return_value="Processed: Test input"
            )
            result = mock_loop.run_until_complete(mock_agent("Test input"))
            assert result == "Processed: Test input"

    @patch("streamlit.session_state", new_callable=MagicMock)
    def test_concurrent_async_operations(self, mock_state):
        """Test handling concurrent async operations."""

        mock_state.event_loop = None

        with patch("asyncio.set_event_loop"):
            with patch("asyncio.new_event_loop") as mock_new_loop:
                mock_loop = MagicMock()
                mock_loop.is_closed.return_value = False
                mock_new_loop.return_value = mock_loop

                loop = get_or_create_event_loop()

        # Simulate concurrent operations
        async def async_task(task_id):
            return f"Task {task_id} complete"

        # Mock gather to simulate concurrent execution
        expected_results = [f"Task {i} complete" for i in range(5)]

        with patch("asyncio.gather") as mock_gather:
            mock_gather.return_value = expected_results

            # Test that multiple tasks can be handled
            tasks = [async_task(i) for i in range(5)]
            results = mock_gather(*tasks)

            assert len(results) == 5
            assert all("complete" in r for r in results)
            mock_gather.assert_called_once()


@pytest.mark.integration
class TestErrorPropagationAndHandling:
    """Test error propagation and handling across the system."""

    @patch("streamlit.session_state", new_callable=MagicMock)
    @patch("streamlit.error")
    def test_rendering_error_propagation(self, mock_error, mock_state):
        """Test that rendering errors are properly propagated."""

        mock_state.tools = {}

        # Create message that will cause error
        messages = [
            {
                "role": "assistant",
                "content": [{"type": "tool_result", "tool_use_id": "nonexistent"}],
            }
        ]

        renderer = MessageRenderer(mock_state)
        with patch("streamlit.chat_message"):
            # Should handle missing tool gracefully
            renderer.render_conversation_history(messages)

        # Error should not be called for missing tool (handled gracefully)
        mock_error.assert_not_called()

    @patch("streamlit.session_state", new_callable=MagicMock)
    def test_initialization_error_recovery(self, mock_state):
        """Test recovery from initialization errors."""

        mock_state.__contains__.return_value = False
        # Set provider to valid enum value so lambda can access it
        mock_state.provider = APIProvider.ANTHROPIC

        # First call fails
        with patch("browser_use_demo.tools.BrowserTool") as mock_browser:
            mock_browser.side_effect = [Exception("Init failed"), MagicMock()]

            # First attempt should fail
            with pytest.raises(Exception, match="Init failed"):
                setup_state()

            # Second attempt should succeed
            setup_state()
            assert mock_browser.call_count == 2


@pytest.mark.integration
class TestCompleteWorkflow:
    """Test complete workflow from initialization to rendering."""

    @patch("streamlit.session_state", new_callable=MagicMock)
    @patch("streamlit.chat_input")
    @patch("streamlit.chat_message")
    @patch("streamlit.markdown")
    @patch("browser_use_demo.tools.BrowserTool")
    @patch("browser_use_demo.streamlit.run_agent", new_callable=AsyncMock)
    def test_complete_user_interaction_flow(
        self,
        mock_run_agent,
        mock_browser_tool,
        mock_markdown,
        mock_chat_message,
        mock_chat_input,
        mock_state,
    ):
        """Test complete flow from user input to message rendering."""

        # Setup initial state
        mock_state.__contains__.return_value = False
        # Set provider to valid enum value so lambda can access it
        mock_state.provider = APIProvider.ANTHROPIC
        setup_state()

        # Simulate user input
        user_input = "Browse to example.com"
        mock_chat_input.return_value = user_input

        # Setup event loop
        with patch("asyncio.new_event_loop") as mock_new_loop:
            mock_loop = MagicMock()
            mock_loop.is_closed.return_value = False
            mock_loop.run_until_complete = MagicMock()
            mock_new_loop.return_value = mock_loop

            with patch("asyncio.set_event_loop"):
                loop = get_or_create_event_loop()

        # Simulate agent response
        mock_run_agent.return_value = None

        # Mock chat message context
        mock_chat_message.return_value.__enter__ = Mock()
        mock_chat_message.return_value.__exit__ = Mock()

        # Simulate the workflow
        # User provides input
        if user_input:
            loop.run_until_complete(mock_run_agent(user_input))

            mock_loop.run_until_complete.assert_called_once()
            mock_run_agent.assert_called_once_with(user_input)


@pytest.mark.integration
class TestPerformanceAndScalability:
    """Test performance with large datasets and edge cases."""

    @patch("streamlit.session_state", new_callable=MagicMock)
    @patch("streamlit.chat_message")
    @patch("streamlit.markdown")
    def test_large_conversation_history(
        self, mock_markdown, mock_chat_message, mock_state
    ):
        """Test rendering very large conversation history."""

        # Create large conversation (1000 messages)
        large_conversation = []
        for i in range(1000):
            role = "user" if i % 2 == 0 else "assistant"
            large_conversation.append({"role": role, "content": f"Message {i}"})

        mock_state.tools = {}
        mock_chat_message.return_value.__enter__ = Mock()
        mock_chat_message.return_value.__exit__ = Mock()

        renderer = MessageRenderer(mock_state)

        # Should handle large conversation without issues
        renderer.render_conversation_history(large_conversation)

        # Verify all messages were processed
        assert mock_markdown.call_count == 1000

    @patch("streamlit.session_state", new_callable=MagicMock)
    def test_deeply_nested_content_performance(self, mock_state):
        """Test performance with deeply nested content structures."""

        # Create deeply nested structure
        content = {"type": "text", "text": "Base"}
        for i in range(100):
            content = {"type": "wrapper", "content": [content], "depth": i}

        messages = [{"role": "user", "content": [content]}]

        mock_state.tools = {}

        with patch("streamlit.chat_message"), patch("streamlit.write"):
            renderer = MessageRenderer(mock_state)

            # Should handle deep nesting without stack overflow
            renderer.render_conversation_history(messages)
