"""Exercise model selection across application upgrades."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, call

import httpx2 as httpx
import pytest
from anthropic import Anthropic
from streamlit.testing.v1 import AppTest

from browser_use_demo.loop import (
    APIProvider,
    _maybe_filter_to_n_most_recent_images,
    sampling_loop,
)
from browser_use_demo.message_renderer import MessageRenderer, Sender
from browser_use_demo.streamlit import PROVIDER_TO_DEFAULT_MODEL_NAME, run_agent
from browser_use_demo.tools import ToolResult


@pytest.fixture
def app(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return AppTest.from_file(
        Path(__file__).parents[1] / "browser_use_demo" / "streamlit.py"
    )


def test_fresh_session_selects_default(app):
    app.run()

    assert not app.exception
    assert app.selectbox(key="model").value == "claude-sonnet-5-5"


@pytest.mark.parametrize("model", ["claude-sonnet-4-5-20250929", "claude-sonnet-4-5"])
def test_existing_session_migrates_retiring_model(app, model):
    messages = [{"role": "user", "content": "Keep my conversation"}]
    app.session_state["model"] = model
    app.session_state["messages"] = messages

    app.run()

    assert not app.exception
    assert app.selectbox(key="model").value == "claude-sonnet-5-5"
    assert app.session_state["messages"] == messages

    app.run()

    assert not app.exception
    assert app.selectbox(key="model").value == "claude-sonnet-5-5"
    assert app.session_state["messages"] == messages


@pytest.mark.parametrize(
    "model",
    [
        "claude-sonnet-5-5",
        "claude-opus-5-5",
        "claude-haiku-4-5-20251001",
    ],
)
def test_existing_session_preserves_supported_selection(app, model):
    app.session_state["model"] = model

    app.run()

    assert not app.exception
    assert app.selectbox(key="model").value == model


@pytest.mark.parametrize("provider", [APIProvider.BEDROCK, APIProvider.VERTEX])
def test_partner_model_is_not_migrated(provider):
    app = AppTest.from_string(
        "from browser_use_demo.streamlit import setup_state\nsetup_state()"
    )
    model = PROVIDER_TO_DEFAULT_MODEL_NAME[provider]
    app.session_state["provider"] = provider
    app.session_state["model"] = model

    app.run()

    assert not app.exception
    assert app.session_state["model"] == model


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "thinking_blocks",
    [
        [],
        [{"type": "thinking", "thinking": "Plan the screenshot", "signature": "sig_plan"}],
        [{"type": "thinking", "thinking": "", "signature": "sig_empty"}],
        [{"type": "redacted_thinking", "data": "encrypted_thinking"}],
        [
            {"type": "thinking", "thinking": "Plan the screenshot", "signature": "sig_plan"},
            {"type": "redacted_thinking", "data": "encrypted_thinking"},
            {"type": "thinking", "thinking": "", "signature": "sig_empty"},
        ],
    ],
    ids=["no-thinking", "thinking", "empty-thinking", "redacted-thinking", "mixed-thinking"],
)
async def test_default_model_tool_roundtrip(monkeypatch, thinking_blocks, mock_streamlit):
    requests = []
    model = PROVIDER_TO_DEFAULT_MODEL_NAME[APIProvider.ANTHROPIC]
    assistant_content = [
        *thinking_blocks,
        {"type": "text", "text": "Taking a screenshot"},
        {
            "type": "tool_use",
            "id": "tool_screenshot",
            "name": "browser",
            "input": {"action": "screenshot"},
        },
    ]
    renderer = MessageRenderer(mock_streamlit["session_state"])

    def respond(request):
        assert request.method == "POST"
        assert request.url.path == "/v1/messages"
        body = json.loads(request.content)
        requests.append(body)
        assert body["model"] == "claude-sonnet-5-5"
        assert body["tools"][0]["name"] == "browser"
        assert not {"temperature", "top_p", "top_k", "thinking", "tool_choice"} & body.keys()
        assert body["messages"][-1]["role"] == "user"

        if len(requests) == 1:
            content = assistant_content
            stop_reason = "tool_use"
        else:
            content = [{"type": "text", "text": "Done"}]
            stop_reason = "end_turn"

        return httpx.Response(
            200,
            json={
                "id": f"msg_{len(requests)}",
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": content,
                "stop_reason": stop_reason,
                "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 10},
            },
        )

    browser = AsyncMock(return_value=ToolResult(output="Screenshot taken"))
    browser.name = "browser"
    browser.to_params = Mock(
        return_value={
            "name": "browser",
            "input_schema": {"type": "object", "properties": {}},
        }
    )
    with Anthropic(
        api_key="test-key",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    ) as client:
        monkeypatch.setattr("browser_use_demo.loop.Anthropic", lambda **kwargs: client)
        messages = await sampling_loop(
            model=model,
            provider=APIProvider.ANTHROPIC,
            system_prompt_suffix="",
            messages=[{"role": "user", "content": "Take a screenshot"}],
            output_callback=lambda block: renderer.render(Sender.BOT, block),
            tool_output_callback=lambda result, tool_id: None,
            api_response_callback=lambda *args: None,
            api_key="test-key",
            browser_tool=browser,
        )

    assert len(requests) == 2
    browser.assert_awaited_once_with(action="screenshot")
    assert [message["role"] for message in requests[1]["messages"]] == [
        "user",
        "assistant",
        "user",
    ]
    assert requests[1]["messages"][1]["content"] == assistant_content
    assert requests[1]["messages"][2]["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "tool_screenshot",
        "content": [{"type": "text", "text": "Screenshot taken"}],
    }
    assert messages[-1].get("content") == [{"type": "text", "text": "Done"}]
    assert mock_streamlit["write"].call_args_list == [
        call("Taking a screenshot"),
        call("Done"),
    ]
    assert mock_streamlit["chat_message"].call_count == 3

    for key in ("write", "code", "chat_message"):
        mock_streamlit[key].reset_mock()
    renderer.render_conversation_history(messages)
    assert mock_streamlit["write"].call_args_list == [
        call("Taking a screenshot"),
        call("Done"),
    ]
    assert mock_streamlit["code"].call_count == 1
    assert mock_streamlit["chat_message"].call_count == 5


@pytest.mark.asyncio
async def test_live_output_skips_thinking_blocks(monkeypatch, mock_streamlit):
    thinking_blocks = [
        {"type": "thinking", "thinking": "", "signature": "sig_empty"},
        {"type": "redacted_thinking", "data": "encrypted_thinking"},
    ]
    content = [*thinking_blocks, {"type": "text", "text": "Done"}]

    async def respond(**kwargs):
        for block in content:
            kwargs["output_callback"](block)
        return [*kwargs["messages"], {"role": "assistant", "content": content}]

    monkeypatch.setattr("browser_use_demo.streamlit.sampling_loop", respond)
    monkeypatch.setattr("streamlit.rerun", Mock())

    await run_agent("Take a screenshot")

    state = mock_streamlit["session_state"]
    assert state.messages[-1]["content"] == content
    assert state.active_messages == [("assistant", content[-1])]
    assert mock_streamlit["write"].call_args_list == [call("Done")]
    assert mock_streamlit["chat_message"].call_count == 2


def test_image_filter_preserves_thinking_blocks():
    assistant_content = [
        {"type": "thinking", "thinking": "", "signature": "sig_empty"},
        {"type": "redacted_thinking", "data": "encrypted_thinking"},
    ]
    images = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}}
        for data in ("old", "recent")
    ]
    messages = [
        {"role": "user", "content": images},
        {"role": "assistant", "content": assistant_content},
    ]

    _maybe_filter_to_n_most_recent_images(messages, images_to_keep=1, min_removal_threshold=1)

    assert messages[0]["content"] == [images[-1]]
    assert messages[1]["content"] == assistant_content
