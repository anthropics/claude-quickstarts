"""Shared fixtures and configuration for tests."""

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from browser_use_demo.tools import ToolResult


@pytest.fixture
def mock_streamlit():
    """Mock Streamlit module and session_state."""
    with patch("streamlit.session_state") as mock_state:
        # Initialize with default values
        mock_state.hide_screenshots = False
        mock_state.tools = {}
        mock_state.messages = []
        mock_state.api_key = "test-key"
        mock_state.provider = MagicMock()
        mock_state.event_loop = None

        # Mock other streamlit components
        with patch("streamlit.chat_message") as mock_chat:
            mock_chat.return_value.__enter__ = Mock()
            mock_chat.return_value.__exit__ = Mock()

            with patch("streamlit.markdown") as mock_markdown:
                with patch("streamlit.write") as mock_write:
                    with patch("streamlit.error") as mock_error:
                        with patch("streamlit.code") as mock_code:
                            with patch("streamlit.image") as mock_image:
                                yield {
                                    "session_state": mock_state,
                                    "chat_message": mock_chat,
                                    "markdown": mock_markdown,
                                    "write": mock_write,
                                    "error": mock_error,
                                    "code": mock_code,
                                    "image": mock_image,
                                }


@pytest.fixture
def mock_browser_tool():
    """Mock BrowserTool to avoid Playwright dependencies."""
    with patch("browser_use_demo.tools.BrowserTool") as mock_tool:
        mock_instance = MagicMock()
        mock_tool.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def sample_tool_result():
    """Create sample ToolResult objects for testing."""
    return {
        "success": ToolResult(output="Success message"),
        "error": ToolResult(error="Error message"),
        "with_image": ToolResult(
            output="With screenshot",
            base64_image="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
        ),
        "empty": ToolResult(),
        "all_fields": ToolResult(
            output="Output text",
            error="Error text",
            base64_image="base64data",
            system="System message",
        ),
    }


@pytest.fixture
def sample_messages():
    """Provide various message structures for testing edge cases."""
    return [
        # Normal messages
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        # Complex content structures
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Multiple items"},
                {"type": "image", "source": "data:image/png;base64,abc123"},
            ],
        },
        # Assistant with tool results
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Let me help with that"},
                {
                    "type": "tool_use",
                    "name": "browser",
                    "input": {"url": "example.com"},
                },
                {"type": "tool_result", "tool_use_id": "tool_123"},
            ],
        },
        # Edge cases
        {"role": "user", "content": ""},  # Empty content
        {"role": "assistant", "content": None},  # None content
        {"role": "unknown", "content": "Unknown role"},  # Unknown role
        {"role": "user"},  # Missing content field
        {"content": "No role"},  # Missing role field
        # Unicode and special characters
        {"role": "user", "content": "Hello 世界 🌍 \n\t\r"},
        # Very long content
        {"role": "user", "content": "x" * 10000},
        # Nested structures
        {
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": "Nested",
                    "metadata": {"nested": {"deeply": {"value": 123}}},
                }
            ],
        },
    ]


@pytest.fixture
def edge_case_messages():
    """Messages specifically designed to test edge cases and error conditions."""
    return {
        "empty_list": [],
        "none": None,
        "malformed_dict": {"not": "valid", "message": "structure"},
        "circular_ref": _create_circular_reference(),
        "missing_tool": {
            "role": "assistant",
            "content": [{"type": "tool_result", "tool_use_id": "nonexistent_tool"}],
        },
        "invalid_types": [
            {"role": 123, "content": "Invalid role type"},
            {"role": "user", "content": {"invalid": "content structure"}},
        ],
        "huge_message": {
            "role": "user",
            "content": [{"type": "text", "text": "x" * 1000000}],
        },
    }


def _create_circular_reference():
    """Helper to create a message with circular reference."""
    msg = {"role": "user", "content": []}
    msg["content"].append(msg)  # Circular reference
    return msg


@pytest.fixture
def mock_asyncio_loop():
    """Mock asyncio event loop for testing."""
    loop = Mock(spec=asyncio.AbstractEventLoop)
    loop.is_closed.return_value = False
    loop.run_until_complete = Mock(side_effect=lambda coro: asyncio.run(coro))
    return loop


@pytest.fixture
def mock_environment(monkeypatch):
    """Mock environment variables for testing."""
    env_vars = {
        "ANTHROPIC_API_KEY": "test-api-key",
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


@pytest.fixture
def clean_environment(monkeypatch):
    """Remove environment variables for testing missing env scenarios."""
    keys_to_remove = [
        "ANTHROPIC_API_KEY",
    ]

    for key in keys_to_remove:
        monkeypatch.delenv(key, raising=False)

    return keys_to_remove


@pytest.fixture
def mock_provider():
    """Mock APIProvider enum."""
    with patch("browser_use_demo.loop.APIProvider") as mock:
        mock.ANTHROPIC = "anthropic"
        mock.BEDROCK = "bedrock"
        mock.VERTEX = "vertex"
        yield mock


@pytest.fixture
def mock_api_response_with_text_and_tools():
    """Mock API response containing both text and tool uses."""
    response = Mock()
    response.content = [
        Mock(type="text", text="I'll help you with that task"),
        Mock(
            type="tool_use",
            id="tool_001",
            name="browser",
            input={"action": "screenshot"}
        ),
        Mock(type="text", text="Here's what I found"),
        Mock(
            type="tool_use",
            id="tool_002",
            name="browser",
            input={"action": "navigate", "url": "example.com"}
        )
    ]
    return response


@pytest.fixture
def mock_tool_collection():
    """Mock ToolCollection for testing."""
    from unittest.mock import AsyncMock

    mock_browser = AsyncMock()
    mock_browser.return_value = ToolResult(output="Tool executed successfully")

    collection = Mock()
    collection.tool_map = {"browser": mock_browser}
    collection.to_params = Mock(return_value=[
        {
            "name": "browser",
            "description": "Browser automation tool",
            "input_schema": {}
        }
    ])

    return collection


@pytest.fixture
def sample_mixed_content_messages():
    """Sample messages with mixed text and tool content."""
    return [
        {
            "role": "user",
            "content": "Can you help me navigate and take a screenshot?"
        },
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Sure, I'll navigate to the page first"},
                {
                    "type": "tool_use",
                    "id": "tool_nav",
                    "name": "browser",
                    "input": {"action": "navigate", "url": "example.com"}
                },
                {"type": "text", "text": "Now taking a screenshot"},
                {
                    "type": "tool_use",
                    "id": "tool_shot",
                    "name": "browser",
                    "input": {"action": "screenshot"}
                }
            ]
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tool_nav",
                    "content": [{"type": "text", "text": "Navigation successful"}]
                },
                {
                    "type": "tool_result",
                    "tool_use_id": "tool_shot",
                    "content": [
                        {"type": "text", "text": "Screenshot taken"},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": "base64imagedata"
                            }
                        }
                    ]
                }
            ]
        }
    ]
