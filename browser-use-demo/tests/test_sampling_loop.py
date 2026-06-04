"""
Comprehensive tests for the sampling loop and message handling.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from browser_use_demo.loop import APIProvider, sampling_loop
from browser_use_demo.message_handler import (
    MessageBuilder,
    ResponseProcessor,
)
from browser_use_demo.tools import ToolResult


class TestResponseProcessor:
    """Test the ResponseProcessor class."""

    def test_process_response_text_only(self):
        """Test processing a response with only text content."""
        mock_response = Mock()
        mock_response.content = [
            Mock(type="text", text="This is a text response")
        ]

        processor = ResponseProcessor()
        result = processor.process_response(mock_response)

        assert result.has_text is True
        assert result.has_tools is False
        assert len(result.assistant_content) == 1
        assert result.assistant_content[0]["type"] == "text"
        assert result.assistant_content[0]["text"] == "This is a text response"
        assert len(result.tool_uses) == 0

    def test_process_response_tool_only(self):
        """Test processing a response with only tool use."""
        mock_response = Mock()
        mock_tool_use = Mock(
            type="tool_use",
            id="tool_123",
            name="browser",
            input={"action": "screenshot"}
        )
        mock_response.content = [mock_tool_use]

        processor = ResponseProcessor()
        result = processor.process_response(mock_response)

        assert result.has_text is False
        assert result.has_tools is True
        assert len(result.assistant_content) == 1
        assert result.assistant_content[0]["type"] == "tool_use"
        assert len(result.tool_uses) == 1

    def test_process_response_mixed_content(self):
        """Test processing a response with both text and tool use."""
        mock_response = Mock()
        mock_response.content = [
            Mock(type="text", text="Let me take a screenshot"),
            Mock(
                type="tool_use",
                id="tool_456",
                name="browser",
                input={"action": "screenshot"}
            )
        ]

        processor = ResponseProcessor()
        result = processor.process_response(mock_response)

        assert result.has_text is True
        assert result.has_tools is True
        assert len(result.assistant_content) == 2
        assert result.assistant_content[0]["type"] == "text"
        assert result.assistant_content[0]["text"] == "Let me take a screenshot"
        assert result.assistant_content[1]["type"] == "tool_use"
        assert len(result.tool_uses) == 1

    def test_execute_tools_success(self):
        """Test successful tool execution."""

        async def run_test():
            mock_tool = AsyncMock(return_value=ToolResult(output="Tool executed"))
            mock_collection = Mock()
            mock_collection.tool_map = {"browser": mock_tool}

            tool_uses = [
                {
                    "type": "tool_use",
                    "id": "tool_789",
                    "name": "browser",
                    "input": {"action": "screenshot"}
                }
            ]

            processor = ResponseProcessor()
            results = await processor.execute_tools(tool_uses, mock_collection)

            assert len(results) == 1
            assert results[0]["type"] == "tool_result"
            assert results[0]["tool_use_id"] == "tool_789"
            assert any(
                block.get("text") == "Tool executed"
                for block in results[0]["content"]
            )

        asyncio.run(run_test())

    def test_execute_tools_with_error(self):
        """Test tool execution with error."""

        async def run_test():
            mock_tool = AsyncMock(side_effect=Exception("Tool failed"))
            mock_collection = Mock()
            mock_collection.tool_map = {"browser": mock_tool}

            tool_uses = [
                {
                    "type": "tool_use",
                    "id": "tool_error",
                    "name": "browser",
                    "input": {"action": "invalid"}
                }
            ]

            processor = ResponseProcessor()
            results = await processor.execute_tools(tool_uses, mock_collection)

            assert len(results) == 1
            assert results[0]["type"] == "tool_result"
            assert results[0]["is_error"] is True
            assert any(
                "Tool failed" in block.get("text", "")
                for block in results[0]["content"]
            )

        asyncio.run(run_test())

    def test_build_tool_result_with_image(self):
        """Test building tool result with base64 image."""
        result = ToolResult(base64_image="base64_data_here")
        processor = ResponseProcessor()

        tool_result = processor._build_tool_result(result, "tool_img")

        assert tool_result["type"] == "tool_result"
        assert tool_result["tool_use_id"] == "tool_img"
        assert any(
            block.get("type") == "image"
            for block in tool_result["content"]
        )

    def test_build_tool_result_with_text_extraction_markers(self):
        """Test handling of text extraction markers in tool results."""
        result = ToolResult(
            output="__PAGE_EXTRACTED__\nSome content\n__FULL_CONTENT__\nThe actual content"
        )
        processor = ResponseProcessor()

        tool_result = processor._build_tool_result(result, "tool_extract")

        assert any(
            block.get("text") == "The actual content"
            for block in tool_result["content"]
        )


class TestMessageBuilder:
    """Test the MessageBuilder class."""

    def test_add_assistant_message(self):
        """Test adding an assistant message."""
        messages = []
        content = [
            {"type": "text", "text": "Hello"},
            {"type": "tool_use", "id": "123", "name": "test", "input": {}}
        ]

        builder = MessageBuilder()
        builder.add_assistant_message(messages, content)

        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"
        assert messages[0]["content"] == content

    def test_add_assistant_message_empty_content(self):
        """Test that empty content is not added."""
        messages = []
        content = []

        builder = MessageBuilder()
        builder.add_assistant_message(messages, content)

        assert len(messages) == 0

    def test_add_tool_results(self):
        """Test adding tool results."""
        messages = []
        tool_results = [
            {
                "type": "tool_result",
                "tool_use_id": "123",
                "content": [{"type": "text", "text": "Result"}]
            }
        ]

        builder = MessageBuilder()
        builder.add_tool_results(messages, tool_results)

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == tool_results

    def test_add_tool_results_empty(self):
        """Test that empty tool results are not added."""
        messages = []
        tool_results = []

        builder = MessageBuilder()
        builder.add_tool_results(messages, tool_results)

        assert len(messages) == 0

    def test_ensure_message_integrity_valid(self):
        """Test message integrity validation with valid messages."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": [{"type": "text", "text": "Hi"}]},
        ]

        builder = MessageBuilder()
        assert builder.ensure_message_integrity(messages) is True

    def test_ensure_message_integrity_missing_role(self):
        """Test message integrity with missing role."""
        messages = [
            {"content": "Hello"},
        ]

        builder = MessageBuilder()
        assert builder.ensure_message_integrity(messages) is False

    def test_ensure_message_integrity_missing_content(self):
        """Test message integrity with missing content."""
        messages = [
            {"role": "user"},
        ]

        builder = MessageBuilder()
        assert builder.ensure_message_integrity(messages) is False

    def test_ensure_message_integrity_empty_list_content(self):
        """Test message integrity with empty content list."""
        messages = [
            {"role": "user", "content": []},
        ]

        builder = MessageBuilder()
        assert builder.ensure_message_integrity(messages) is False

    def test_extract_text_from_message(self):
        """Test extracting text from assistant message."""
        message = {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "First part"},
                {"type": "tool_use", "id": "123", "name": "test", "input": {}},
                {"type": "text", "text": "Second part"}
            ]
        }

        builder = MessageBuilder()
        text = builder.extract_text_from_message(message)

        assert text == "First part Second part"

    def test_extract_text_from_message_no_text(self):
        """Test extracting text when there's no text content."""
        message = {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "123", "name": "test", "input": {}}
            ]
        }

        builder = MessageBuilder()
        text = builder.extract_text_from_message(message)

        assert text is None

    def test_extract_text_from_user_message(self):
        """Test that text extraction returns None for non-assistant messages."""
        message = {
            "role": "user",
            "content": "User message"
        }

        builder = MessageBuilder()
        text = builder.extract_text_from_message(message)

        assert text is None


@pytest.mark.integration
class TestSamplingLoopIntegration:
    """Integration tests for the sampling loop."""

    @patch("browser_use_demo.loop.Anthropic")
    def test_sampling_loop_preserves_text_with_tools(self, mock_anthropic):
        """Test that text is preserved when tools are used."""

        async def run_test():
            mock_client = Mock()
            mock_anthropic.return_value = mock_client

            mock_response = Mock()
            mock_response.content = [
                Mock(type="text", text="I'll help you with that"),
                Mock(
                    type="tool_use",
                    id="tool_001",
                    name="browser",
                    input={"action": "screenshot"}
                )
            ]

            mock_client.beta.messages.create = Mock(return_value=mock_response)

            mock_browser = AsyncMock()
            mock_browser.return_value = ToolResult(output="Screenshot taken")

            messages = [{"role": "user", "content": "Take a screenshot"}]
            output_messages = []
            tool_outputs = {}

            def output_callback(content):
                output_messages.append(content)

            def tool_output_callback(result, tool_id):
                tool_outputs[tool_id] = result

            updated_messages = await sampling_loop(
                model="claude-sonnet-4-5",
                provider=APIProvider.ANTHROPIC,
                system_prompt_suffix="",
                messages=messages,
                output_callback=output_callback,
                tool_output_callback=tool_output_callback,
                api_response_callback=lambda *args: None,
                api_key="test_key",
                browser_tool=mock_browser
            )

            api_call_args = mock_client.beta.messages.create.call_args[1]
            assert api_call_args["tool_choice"] == {"type": "auto"}

            assert len(output_messages) >= 2
            assert any(
                msg.get("type") == "text" and "help you" in msg.get("text", "")
                for msg in output_messages
            )
            assert any(msg.get("type") == "tool_use" for msg in output_messages)

            assistant_msgs = [m for m in updated_messages if m["role"] == "assistant"]
            assert len(assistant_msgs) > 0

            last_assistant = assistant_msgs[-1]
            assert isinstance(last_assistant["content"], list)

            has_text = any(
                block.get("type") == "text"
                for block in last_assistant["content"]
            )
            has_tool = any(
                block.get("type") == "tool_use"
                for block in last_assistant["content"]
            )

            assert has_text and has_tool, "Assistant message should contain both text and tool use"

        asyncio.run(run_test())

    @patch("browser_use_demo.loop.Anthropic")
    def test_sampling_loop_text_only_response(self, mock_anthropic):
        """Test handling of text-only responses."""

        async def run_test():
            mock_client = Mock()
            mock_anthropic.return_value = mock_client

            mock_response = Mock()
            mock_response.content = [
                Mock(type="text", text="This is just a text response")
            ]

            mock_client.beta.messages.create = Mock(return_value=mock_response)

            messages = [{"role": "user", "content": "Hello"}]

            updated_messages = await sampling_loop(
                model="claude-sonnet-4-5",
                provider=APIProvider.ANTHROPIC,
                system_prompt_suffix="",
                messages=messages,
                output_callback=lambda x: None,
                tool_output_callback=lambda r, i: None,
                api_response_callback=lambda *args: None,
                api_key="test_key"
            )

            assert len(updated_messages) == 2
            assert updated_messages[-1]["role"] == "assistant"
            assert any(
                block.get("text") == "This is just a text response"
                for block in updated_messages[-1]["content"]
            )

        asyncio.run(run_test())

    @patch("browser_use_demo.loop.Anthropic")
    def test_sampling_loop_multiple_tools_with_text(self, mock_anthropic):
        """Test handling of multiple tool uses with text."""

        async def run_test():
            mock_client = Mock()
            mock_anthropic.return_value = mock_client

            mock_response = Mock()
            mock_response.content = [
                Mock(type="text", text="I'll perform multiple actions"),
                Mock(
                    type="tool_use",
                    id="tool_001",
                    name="browser",
                    input={"action": "screenshot"}
                ),
                Mock(type="text", text="Now navigating"),
                Mock(
                    type="tool_use",
                    id="tool_002",
                    name="browser",
                    input={"action": "navigate", "url": "example.com"}
                )
            ]

            mock_client.beta.messages.create = Mock(return_value=mock_response)

            mock_browser = AsyncMock()
            mock_browser.return_value = ToolResult(output="Action completed")

            messages = [{"role": "user", "content": "Do multiple things"}]

            updated_messages = await sampling_loop(
                model="claude-sonnet-4-5",
                provider=APIProvider.ANTHROPIC,
                system_prompt_suffix="",
                messages=messages,
                output_callback=lambda x: None,
                tool_output_callback=lambda r, i: None,
                api_response_callback=lambda *args: None,
                api_key="test_key",
                browser_tool=mock_browser
            )

            assistant_msgs = [m for m in updated_messages if m["role"] == "assistant"]
            last_assistant = assistant_msgs[-1]

            text_blocks = [
                block for block in last_assistant["content"]
                if block.get("type") == "text"
            ]
            tool_blocks = [
                block for block in last_assistant["content"]
                if block.get("type") == "tool_use"
            ]

            assert len(text_blocks) == 2
            assert len(tool_blocks) == 2

        asyncio.run(run_test())

    @patch("browser_use_demo.loop.Anthropic")
    def test_tool_choice_parameter_set(self, mock_anthropic):
        """Test that tool_choice is explicitly set to auto."""

        async def run_test():
            mock_client = Mock()
            mock_anthropic.return_value = mock_client

            mock_response = Mock()
            mock_response.content = [Mock(type="text", text="Response")]

            mock_client.beta.messages.create = Mock(return_value=mock_response)

            await sampling_loop(
                model="claude-sonnet-4-5",
                provider=APIProvider.ANTHROPIC,
                system_prompt_suffix="",
                messages=[{"role": "user", "content": "Test"}],
                output_callback=lambda x: None,
                tool_output_callback=lambda r, i: None,
                api_response_callback=lambda *args: None,
                api_key="test_key"
            )

            call_args = mock_client.beta.messages.create.call_args[1]
            assert "tool_choice" in call_args
            assert call_args["tool_choice"] == {"type": "auto"}

        asyncio.run(run_test())


def _make_tool_result_with_image(tool_use_id: str, data: str) -> dict:
    """Build a user-message tool_result block containing a single image.

    Mirrors the shape produced by ResponseProcessor._build_tool_result, i.e.
    the image lives nested inside the tool_result's own content list.
    """
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": data,
                },
            }
        ],
    }


def _count_images(messages: list[dict]) -> int:
    """Count screenshot images nested inside tool_result blocks."""
    return sum(
        1
        for message in messages
        if isinstance(message.get("content"), list)
        for block in message["content"]
        if isinstance(block, dict) and block.get("type") == "tool_result"
        for inner in block.get("content", [])
        if isinstance(inner, dict) and inner.get("type") == "image"
    )


class TestImageTruncation:
    """Tests for the `only_n_most_recent_images` screenshot-truncation feature."""

    def test_filter_helper_removes_nested_screenshots(self):
        """The helper must descend into tool_result blocks (where screenshots live).

        Screenshots are stored nested inside ``tool_result`` blocks, not as
        top-level ``image`` blocks in user content. The helper must count and
        remove those nested images for truncation to do anything at all.
        """
        from browser_use_demo.loop import _maybe_filter_to_n_most_recent_images

        # 15 accumulated screenshots, keep the 3 most recent.
        messages = [
            {
                "role": "user",
                "content": [_make_tool_result_with_image(f"tool_{i}", f"img_{i}")],
            }
            for i in range(15)
        ]

        assert _count_images(messages) == 15

        _maybe_filter_to_n_most_recent_images(
            messages,
            images_to_keep=3,
            min_removal_threshold=1,
        )

        remaining = _count_images(messages)
        assert remaining == 3, (
            f"expected 3 most-recent screenshots to remain, found {remaining}"
        )
        # The retained screenshots must be the most recent ones.
        kept_data = [
            inner["source"]["data"]
            for message in messages
            if isinstance(message.get("content"), list)
            for block in message["content"]
            if isinstance(block, dict) and block.get("type") == "tool_result"
            for inner in block.get("content", [])
            if isinstance(inner, dict) and inner.get("type") == "image"
        ]
        assert kept_data == ["img_12", "img_13", "img_14"]

    @patch("browser_use_demo.loop.Anthropic")
    def test_sampling_loop_truncates_accumulated_images(self, mock_anthropic):
        """sampling_loop must apply truncation when only_n_most_recent_images is set.

        Runs the loop over a message history that already holds many
        accumulated screenshots. With truncation wired into the loop, only the
        N most recent screenshots survive; without it (the bug) all of them
        remain. The model returns a text-only response so the loop terminates
        after a single iteration.
        """

        async def run_test():
            mock_client = Mock()
            mock_anthropic.return_value = mock_client

            text_response = Mock()
            text_response.content = [Mock(type="text", text="done")]
            mock_client.beta.messages.create = Mock(return_value=text_response)

            mock_browser = AsyncMock()

            # Seed history with 12 prior screenshots.
            messages = [
                {
                    "role": "user",
                    "content": [_make_tool_result_with_image(f"tool_{i}", f"img_{i}")],
                }
                for i in range(12)
            ]

            await sampling_loop(
                model="claude-sonnet-4-5",
                provider=APIProvider.ANTHROPIC,
                system_prompt_suffix="",
                messages=messages,
                output_callback=lambda x: None,
                tool_output_callback=lambda r, i: None,
                api_response_callback=lambda *args: None,
                api_key="test_key",
                only_n_most_recent_images=3,
                browser_tool=mock_browser,
            )

            remaining = _count_images(messages)
            assert remaining == 3, (
                "sampling_loop should truncate to only_n_most_recent_images=3 "
                f"screenshots, but {remaining} remain"
            )
            mock_browser.assert_not_called()

        asyncio.run(run_test())

    def test_filter_helper_image_only_tool_result_gets_sentinel(self):
        """Truncating the sole image from an image-only tool_result must not leave
        content=[], which the Anthropic API rejects with a 400 error.

        The ``screenshot`` / ``zoom`` / ``navigate`` browser actions return a
        ToolResult with output="" (falsy) and base64_image set, so
        _build_tool_result produces a content list with exactly one image block
        and no text block.  When that image is truncated, the guard must insert a
        sentinel text block so the tool_result stays structurally valid.
        """
        from browser_use_demo.loop import _maybe_filter_to_n_most_recent_images

        # Build 5 tool_results that are image-only (no text block).
        messages = [
            {
                "role": "user",
                "content": [_make_tool_result_with_image(f"tool_{i}", f"img_{i}")],
            }
            for i in range(5)
        ]

        assert _count_images(messages) == 5

        # Keep only 3 — so the 2 oldest image-only tool_results lose their sole
        # image.  Without the guard those would be left with content=[].
        _maybe_filter_to_n_most_recent_images(
            messages,
            images_to_keep=3,
            min_removal_threshold=1,
        )

        assert _count_images(messages) == 3

        # Every tool_result must still have at least one content block.
        for message in messages:
            if not isinstance(message.get("content"), list):
                continue
            for block in message["content"]:
                if not (isinstance(block, dict) and block.get("type") == "tool_result"):
                    continue
                content = block.get("content", [])
                assert len(content) > 0, (
                    f"tool_result {block.get('tool_use_id')} has empty content after "
                    "truncation — the API would reject this with a 400"
                )
                # The sentinel must be a text block when the image was removed.
                if not any(
                    isinstance(c, dict) and c.get("type") == "image" for c in content
                ):
                    assert any(
                        isinstance(c, dict) and c.get("type") == "text" for c in content
                    ), (
                        f"tool_result {block.get('tool_use_id')} had its image removed "
                        "but contains no text sentinel"
                    )
