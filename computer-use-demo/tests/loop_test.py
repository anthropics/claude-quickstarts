from unittest import mock

from anthropic.types import TextBlock, ToolUseBlock
from anthropic.types.beta import BetaMessage, BetaMessageParam, BetaTextBlockParam

from computer_use_demo.loop import APIProvider, sampling_loop


async def test_loop():
    client = mock.Mock()
    client.beta.messages.with_raw_response.create.return_value = mock.Mock()
    client.beta.messages.with_raw_response.create.return_value.parse.side_effect = [
        mock.Mock(
            spec=BetaMessage,
            content=[
                TextBlock(type="text", text="Hello"),
                ToolUseBlock(
                    type="tool_use", id="1", name="computer", input={"action": "test"}
                ),
            ],
        ),
        mock.Mock(spec=BetaMessage, content=[TextBlock(type="text", text="Done!")]),
    ]

    tool_collection = mock.AsyncMock()
    tool_collection.run.return_value = mock.Mock(
        output="Tool output", error=None, base64_image=None
    )

    output_callback = mock.Mock()
    tool_output_callback = mock.Mock()
    api_response_callback = mock.Mock()

    with (
        mock.patch("computer_use_demo.loop.Anthropic", return_value=client),
        mock.patch(
            "computer_use_demo.loop.ToolCollection", return_value=tool_collection
        ),
    ):
        messages: list[BetaMessageParam] = [{"role": "user", "content": "Test message"}]
        result = await sampling_loop(
            model="test-model",
            provider=APIProvider.ANTHROPIC,
            system_prompt_suffix="",
            messages=messages,
            output_callback=output_callback,
            tool_output_callback=tool_output_callback,
            api_response_callback=api_response_callback,
            api_key="test-key",
            tool_version="computer_use_20250124",
        )

        assert len(result) == 4
        assert result[0] == {"role": "user", "content": "Test message"}
        assert result[1]["role"] == "assistant"
        assert result[2]["role"] == "user"
        assert result[3]["role"] == "assistant"

        assert client.beta.messages.with_raw_response.create.call_count == 2
        tool_collection.run.assert_called_once_with(
            name="computer", tool_input={"action": "test"}
        )
        output_callback.assert_called_with(
            BetaTextBlockParam(text="Done!", type="text", citations=None)
        )
        assert output_callback.call_count == 3
        assert tool_output_callback.call_count == 1
        assert api_response_callback.call_count == 2


async def _run_loop_and_get_request_kwargs(**loop_kwargs):
    """Drive sampling_loop through a single no-tool-use turn and return the
    kwargs passed to messages.create."""
    client = mock.Mock()
    client.beta.messages.with_raw_response.create.return_value = mock.Mock()
    client.beta.messages.with_raw_response.create.return_value.parse.side_effect = [
        mock.Mock(spec=BetaMessage, content=[TextBlock(type="text", text="Done!")]),
    ]

    with (
        mock.patch("computer_use_demo.loop.Anthropic", return_value=client),
        mock.patch(
            "computer_use_demo.loop.ToolCollection", return_value=mock.AsyncMock()
        ),
    ):
        await sampling_loop(
            model="test-model",
            provider=APIProvider.ANTHROPIC,
            system_prompt_suffix="",
            messages=[{"role": "user", "content": "Test message"}],
            output_callback=mock.Mock(),
            tool_output_callback=mock.Mock(),
            api_response_callback=mock.Mock(),
            api_key="test-key",
            tool_version="computer_use_20250124",
            **loop_kwargs,
        )
    return client.beta.messages.with_raw_response.create.call_args.kwargs


async def test_loop_thinking_off_sends_no_thinking_params():
    kwargs = await _run_loop_and_get_request_kwargs(thinking_mode="off")
    assert kwargs["extra_body"] == {}


async def test_loop_adaptive_thinking_sends_effort():
    kwargs = await _run_loop_and_get_request_kwargs(
        thinking_mode="adaptive", thinking_effort="high"
    )
    assert kwargs["extra_body"] == {
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": "high"},
    }


async def test_loop_extended_thinking_sends_budget():
    kwargs = await _run_loop_and_get_request_kwargs(
        thinking_mode="extended", thinking_budget=2048
    )
    assert kwargs["extra_body"] == {
        "thinking": {"type": "enabled", "budget_tokens": 2048}
    }
