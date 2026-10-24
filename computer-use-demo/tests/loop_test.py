from typing import Any, cast
from unittest import mock

from anthropic import omit
from anthropic.types import TextBlock, ToolUseBlock
from anthropic.types.beta import (
    BetaMessage,
    BetaMessageParam,
    BetaTextBlockParam,
    BetaToolUseBlock,
)

from computer_use_demo.loop import (
    PROMPT_CACHING_BETA_FLAG,
    APIProvider,
    sampling_loop,
)


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
            name="computer", tool_input={"action": "test"}, toolset_name=None
        )
        # A plain (non-member) tool_result must not carry toolset_name.
        assert "toolset_name" not in cast(list[dict[str, Any]], result[2]["content"])[0]
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
        mock.patch("computer_use_demo.loop.AnthropicVertex", return_value=client),
        mock.patch("computer_use_demo.loop.AnthropicBedrock", return_value=client),
        mock.patch(
            "computer_use_demo.loop.ToolCollection", return_value=mock.AsyncMock()
        ),
    ):
        defaults = {
            "model": "test-model",
            "provider": APIProvider.ANTHROPIC,
            "system_prompt_suffix": "",
            "messages": [{"role": "user", "content": "Test message"}],
            "output_callback": mock.Mock(),
            "tool_output_callback": mock.Mock(),
            "api_response_callback": mock.Mock(),
            "api_key": "test-key",
            "tool_version": "computer_use_20250124",
        }
        await sampling_loop(**{**defaults, **loop_kwargs})
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


async def test_loop_toolset_sends_no_beta_header_without_flags():
    """The toolset group has no beta flag. Off the first-party API nothing else
    adds one, so the betas param must be omitted rather than sent empty."""
    kwargs = await _run_loop_and_get_request_kwargs(
        provider=APIProvider.VERTEX, tool_version="computer_toolset_20260801"
    )
    assert kwargs["betas"] is omit


async def test_loop_toolset_on_anthropic_keeps_prompt_caching_beta():
    kwargs = await _run_loop_and_get_request_kwargs(
        tool_version="computer_toolset_20260801"
    )
    assert kwargs["betas"] == [PROMPT_CACHING_BETA_FLAG]


async def test_loop_toolset_member_calls_run_sequentially_and_stop_on_failure():
    client = mock.Mock()
    client.beta.messages.with_raw_response.create.return_value = mock.Mock()
    client.beta.messages.with_raw_response.create.return_value.parse.side_effect = [
        mock.Mock(
            spec=BetaMessage,
            content=[
                BetaToolUseBlock(
                    type="tool_use",
                    id="1",
                    name="key",
                    input={"text": "super"},
                    toolset_name="computer",
                ),
                BetaToolUseBlock(
                    type="tool_use",
                    id="2",
                    name="left_click",
                    input={"coordinate": [100, 200]},
                    toolset_name="computer",
                ),
                BetaToolUseBlock(
                    type="tool_use",
                    id="3",
                    name="screenshot",
                    input={},
                    toolset_name="computer",
                ),
            ],
        ),
        mock.Mock(spec=BetaMessage, content=[TextBlock(type="text", text="Done!")]),
    ]

    tool_collection = mock.AsyncMock()
    tool_collection.run.side_effect = [
        mock.Mock(output="Pressed key: super", error=None, base64_image=None),
        mock.Mock(output=None, error="xdotool failed", base64_image=None),
    ]

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
            output_callback=mock.Mock(),
            tool_output_callback=mock.Mock(),
            api_response_callback=mock.Mock(),
            api_key="test-key",
            tool_version="computer_toolset_20260801",
        )

    # The replayed assistant blocks keep toolset_name.
    assert result[1]["role"] == "assistant"
    assistant_blocks = cast(list[dict[str, Any]], result[1]["content"])
    assert [block.get("toolset_name") for block in assistant_blocks] == [
        "computer",
        "computer",
        "computer",
    ]

    # The failed second call stops execution: the third member call is never
    # run, and its result is the not-executed error.
    assert tool_collection.run.call_count == 2
    tool_collection.run.assert_has_calls(
        [
            mock.call(
                name="key", tool_input={"text": "super"}, toolset_name="computer"
            ),
            mock.call(
                name="left_click",
                tool_input={"coordinate": [100, 200]},
                toolset_name="computer",
            ),
        ]
    )

    assert result[2]["role"] == "user"
    tool_results = cast(list[dict[str, Any]], result[2]["content"])
    assert [block["toolset_name"] for block in tool_results] == [
        "computer",
        "computer",
        "computer",
    ]
    assert [block["is_error"] for block in tool_results] == [False, True, True]
    assert tool_results[2]["content"] == (
        "Not executed: an earlier computer action in this turn failed."
    )
