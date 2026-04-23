from unittest import mock

from anthropic.types import TextBlock, ToolUseBlock
from anthropic.types.beta import BetaMessage, BetaMessageParam

from computer_use_demo.loop import APIProvider, sampling_loop


class _FakeStream:
    def __init__(self, final_message):
        self._final = final_message
        self.events = [
            mock.Mock(type="message_start"),
            mock.Mock(
                type="content_block_delta",
                index=0,
                delta=mock.Mock(type="text_delta", text="Hello"),
            ),
            mock.Mock(type="content_block_stop", index=0),
        ]

    def __aiter__(self):
        async def gen():
            for ev in self.events:
                yield ev

        return gen()

    async def get_final_message(self):
        return self._final


class _FakeStreamManager:
    def __init__(self, final_message):
        self._stream = _FakeStream(final_message)

    async def __aenter__(self):
        return self._stream

    async def __aexit__(self, *a):
        return False


async def test_loop():
    final_messages = [
        mock.Mock(
            spec=BetaMessage,
            content=[
                TextBlock(type="text", text="Hello"),
                ToolUseBlock(
                    type="tool_use", id="1", name="computer", input={"action": "test"}
                ),
            ],
            stop_reason="tool_use",
            usage=None,
            id="msg_1",
        ),
        mock.Mock(
            spec=BetaMessage,
            content=[TextBlock(type="text", text="Done!")],
            stop_reason="end_turn",
            usage=None,
            id="msg_2",
        ),
    ]

    client = mock.Mock()
    client.beta.messages.stream.side_effect = [
        _FakeStreamManager(final_messages[0]),
        _FakeStreamManager(final_messages[1]),
    ]

    tool_collection = mock.Mock()
    tool_collection.to_params.return_value = [
        {"name": "computer", "type": "computer_20251124"},
    ]
    tool_collection.run = mock.AsyncMock(
        return_value=mock.Mock(
            output="Tool output", error=None, base64_image=None, system=None
        )
    )

    output_callback = mock.Mock()
    tool_output_callback = mock.Mock()
    api_response_callback = mock.Mock()
    delta_callback = mock.Mock()

    with (
        mock.patch("computer_use_demo.loop.AsyncAnthropic", return_value=client),
        mock.patch(
            "computer_use_demo.loop.ToolCollection", return_value=tool_collection
        ),
        mock.patch("computer_use_demo.tools.computer.WIDTH", 1024),
        mock.patch("computer_use_demo.tools.computer.HEIGHT", 768),
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
            tool_version="computer_use_20251124",
            delta_callback=delta_callback,
        )

    assert len(result) == 4
    assert result[0] == {"role": "user", "content": "Test message"}
    assert result[1]["role"] == "assistant"
    assert result[2]["role"] == "user"
    assert result[3]["role"] == "assistant"

    assert client.beta.messages.stream.call_count == 2
    tool_collection.run.assert_called_once_with(
        name="computer", tool_input={"action": "test"}
    )
    assert output_callback.call_count == 3
    assert tool_output_callback.call_count == 1
    assert api_response_callback.call_count == 2
    # delta_callback fires per streamed event, 3 events per stream × 2 streams.
    assert delta_callback.call_count == 6
