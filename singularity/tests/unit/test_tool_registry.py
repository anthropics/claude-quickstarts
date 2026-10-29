"""
Tests for ToolRegistry (Fáze 16).
All offline — handlers are simple async mocks; HTTP tools are tested with
a patched httpx.AsyncClient.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.tool_registry import ToolRegistry


@pytest.fixture
def registry():
    return ToolRegistry()


# ── Registration ──────────────────────────────────────────────────────────────

def test_register_adds_tool(registry):
    registry.register("my_tool", "Does stuff", {}, AsyncMock(return_value="ok"))
    assert registry.tool_count() == 1
    assert registry.get_tool("my_tool") is not None


def test_register_invalid_name_raises(registry):
    with pytest.raises(ValueError):
        registry.register("invalid name!", "desc", {}, AsyncMock())


def test_register_invalid_name_empty_raises(registry):
    with pytest.raises(ValueError):
        registry.register("", "desc", {}, AsyncMock())


def test_register_overwrites_existing(registry):
    registry.register("tool", "v1", {}, AsyncMock(return_value="v1"))
    registry.register("tool", "v2", {}, AsyncMock(return_value="v2"))
    assert registry.tool_count() == 1
    assert registry.get_tool("tool").description == "v2"


def test_register_http_adds_tool(registry):
    registry.register_http("hook", "HTTP hook", {}, "https://example.com/cb")
    tool = registry.get_tool("hook")
    assert tool is not None
    assert tool.tool_type == "http"
    assert tool.callback_url == "https://example.com/cb"


def test_register_http_empty_url_raises(registry):
    with pytest.raises(ValueError):
        registry.register_http("tool", "desc", {}, "")


# ── Unregistration ────────────────────────────────────────────────────────────

def test_unregister_returns_true(registry):
    registry.register("rm_me", "desc", {}, AsyncMock())
    assert registry.unregister("rm_me") is True
    assert registry.tool_count() == 0


def test_unregister_missing_returns_false(registry):
    assert registry.unregister("ghost") is False


# ── Listing ───────────────────────────────────────────────────────────────────

def test_list_tools_empty(registry):
    assert registry.list_tools() == []


def test_list_tools_contains_registered(registry):
    registry.register("tool_a", "Tool A", {"type": "object"}, AsyncMock())
    tools = registry.list_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "tool_a"
    assert tools[0]["description"] == "Tool A"
    assert "handler" not in tools[0]  # handler not serialised


def test_list_tools_http_includes_callback_url(registry):
    registry.register_http("remote", "Remote", {}, "https://example.com")
    tools = registry.list_tools()
    assert tools[0]["callback_url"] == "https://example.com"
    assert tools[0]["tool_type"] == "http"


# ── Invocation ────────────────────────────────────────────────────────────────

async def test_invoke_calls_handler(registry):
    handler = AsyncMock(return_value={"answer": 42})
    registry.register("calc", "Calculate", {}, handler)
    result = await registry.invoke("calc", x=1, y=2)
    assert result == {"answer": 42}
    handler.assert_awaited_once_with(x=1, y=2)


async def test_invoke_missing_tool_raises(registry):
    with pytest.raises(KeyError, match="ghost"):
        await registry.invoke("ghost")


async def test_invoke_http_tool_posts_to_callback(registry):
    registry.register_http("hook", "HTTP hook", {}, "https://example.com/cb")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"result": "pong"}
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await registry.invoke("hook", key="val")

    mock_client.post.assert_awaited_once_with("https://example.com/cb", json={"key": "val"})
    assert result == {"result": "pong"}
