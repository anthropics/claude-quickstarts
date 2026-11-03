"""Offline regressions for the agent's automatic cache breakpoint."""

import asyncio
from copy import deepcopy
from unittest.mock import Mock

import pytest
from anthropic.types import Message

from agents import Agent, Tool
from agents.utils.history_util import MessageHistory


def make_history(enable_caching=True):
    client = Mock()
    client.messages.count_tokens.return_value.input_tokens = 1
    return MessageHistory("test-model", "test", 180000, client, enable_caching)


def tool_results(count):
    return [
        {"type": "tool_result", "tool_use_id": f"call_{i}", "content": str(i)}
        for i in range(count)
    ]


@pytest.mark.parametrize("count", [1, 3, 5, 8, 16])
def test_marks_only_the_last_result_without_changing_history(count):
    history = make_history()
    content = tool_results(count)
    original = deepcopy(content)
    asyncio.run(history.add_message("user", content))

    for _ in range(2):
        formatted = history.format_for_api()[0]["content"]
        assert formatted == [
            *original[:-1],
            {**original[-1], "cache_control": {"type": "ephemeral"}},
        ]
        assert history.messages[0]["content"] == original
        assert content == original


def test_preserves_caller_cache_markers_and_earlier_messages():
    history = make_history()
    asyncio.run(history.add_message("user", "first"))
    asyncio.run(history.add_message("assistant", "reply"))
    content = tool_results(2)
    content[0]["cache_control"] = {"type": "ephemeral", "ttl": "1h"}
    asyncio.run(history.add_message("user", content))
    original = deepcopy(history.messages)

    formatted = history.format_for_api()

    assert formatted[:-1] == original[:-1]
    assert formatted[-1]["content"][0] == original[-1]["content"][0]
    assert formatted[-1]["content"][-1]["cache_control"] == {
        "type": "ephemeral"
    }
    assert history.messages == original


def test_disabled_caching_preserves_content():
    history = make_history(enable_caching=False)
    content = tool_results(5)
    content[0]["cache_control"] = {"type": "ephemeral"}
    asyncio.run(history.add_message("user", content))
    assert history.format_for_api() == history.messages


def test_empty_history_and_empty_content():
    history = make_history()
    assert history.format_for_api() == []
    asyncio.run(history.add_message("user", []))
    assert history.format_for_api() == [{"role": "user", "content": []}]


def test_formatted_blocks_remain_shallow_copies():
    history = make_history()
    original = tool_results(2)
    asyncio.run(history.add_message("user", deepcopy(original)))

    formatted = history.format_for_api()[0]["content"]
    for block in formatted:
        block["content"] = "changed by the caller"

    assert history.messages[0]["content"] == original


def test_single_text_message():
    history = make_history()
    asyncio.run(history.add_message("user", "hello"))
    assert history.format_for_api() == [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "hello",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        }
    ]


@pytest.mark.parametrize("count", [5, 16])
def test_agent_sends_one_breakpoint_after_parallel_tools(count):
    class EchoTool(Tool):
        async def execute(self, value):
            return str(value)

    tool = EchoTool(
        name="echo",
        description="Echo a number without external side effects",
        input_schema={
            "type": "object",
            "properties": {"value": {"type": "integer"}},
        },
    )
    requests = []

    def create(**params):
        requests.append(deepcopy(params))
        first = len(requests) == 1
        return Message(
            id=f"message_{len(requests)}",
            type="message",
            role="assistant",
            model="test-model",
            stop_reason="tool_use" if first else "end_turn",
            content=[
                {
                    "type": "tool_use",
                    "id": f"call_{i}",
                    "name": "echo",
                    "input": {"value": i},
                }
                for i in range(count)
            ]
            if first
            else [{"type": "text", "text": "done"}],
            usage={
                "input_tokens": 100,
                "output_tokens": 10,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
        )

    client = Mock()
    client.messages.count_tokens.return_value.input_tokens = 1
    client.messages.create.side_effect = create
    agent = Agent("test", "test", tools=[tool], client=client)

    response = asyncio.run(agent.run_async("Run the tools"))

    assert response.content[0].text == "done"
    assert len(requests) == 2
    content = requests[1]["messages"][-1]["content"]
    expected = tool_results(count)
    assert content == [
        *expected[:-1],
        {**expected[-1], "cache_control": {"type": "ephemeral"}},
    ]
    assert agent.history.messages[-2]["content"] == expected
