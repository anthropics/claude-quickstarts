"""Exercise model selection across application upgrades."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import httpx2 as httpx
import pytest
from anthropic import Anthropic
from streamlit.testing.v1 import AppTest

from browser_use_demo.loop import APIProvider, sampling_loop
from browser_use_demo.streamlit import PROVIDER_TO_DEFAULT_MODEL_NAME
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
    assert app.selectbox(key="model").value == "claude-sonnet-4-6"


@pytest.mark.parametrize("model", ["claude-sonnet-4-5-20250929", "claude-sonnet-4-5"])
def test_existing_session_migrates_retiring_model(app, model):
    messages = [{"role": "user", "content": "Keep my conversation"}]
    app.session_state["model"] = model
    app.session_state["messages"] = messages

    app.run()

    assert not app.exception
    assert app.selectbox(key="model").value == "claude-sonnet-4-6"
    assert app.session_state["messages"] == messages

    app.run()

    assert not app.exception
    assert app.selectbox(key="model").value == "claude-sonnet-4-6"
    assert app.session_state["messages"] == messages


@pytest.mark.parametrize(
    "model",
    [
        "claude-sonnet-4-6",
        "claude-opus-4-5-20251101",
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
async def test_default_model_tool_roundtrip(monkeypatch):
    requests = []
    model = PROVIDER_TO_DEFAULT_MODEL_NAME[APIProvider.ANTHROPIC]

    def respond(request):
        assert request.method == "POST"
        assert request.url.path == "/v1/messages"
        body = json.loads(request.content)
        requests.append(body)
        assert body["model"] == "claude-sonnet-4-6"
        assert body["tools"][0]["name"] == "browser"
        assert not {"temperature", "top_p", "top_k", "thinking"} & body.keys()

        if len(requests) == 1:
            content = [
                {"type": "text", "text": "Taking a screenshot"},
                {
                    "type": "tool_use",
                    "id": "tool_screenshot",
                    "name": "browser",
                    "input": {"action": "screenshot"},
                },
            ]
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
            output_callback=lambda block: None,
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
    assert requests[1]["messages"][1]["content"][1]["id"] == "tool_screenshot"
    assert requests[1]["messages"][2]["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "tool_screenshot",
        "content": [{"type": "text", "text": "Screenshot taken"}],
    }
    assert messages[-1].get("content") == [{"type": "text", "text": "Done"}]
