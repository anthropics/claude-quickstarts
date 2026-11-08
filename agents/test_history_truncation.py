"""Truncation must never separate a tool call from its results (#520)."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

from anthropic.types import Message

from agents.agent import Agent, ModelConfig
from agents.tools.base import Tool
from agents.utils.history_util import MessageHistory


def make_history(context_window_tokens):
    client = Mock()
    client.messages.count_tokens.return_value.input_tokens = 1
    return MessageHistory("test-model", "test", context_window_tokens, client)


def usage(input_tokens, output_tokens=1):
    return SimpleNamespace(
        input_tokens=input_tokens, output_tokens=output_tokens
    )


def tool_use(identifier):
    return {
        "type": "tool_use",
        "id": identifier,
        "name": "lookup",
        "input": {},
    }


def tool_result(identifier):
    return {"type": "tool_result", "tool_use_id": identifier, "content": "ok"}


def add_tool_turn(history, identifier, input_tokens):
    asyncio.run(
        history.add_message(
            "assistant", [tool_use(identifier)], usage(input_tokens)
        )
    )
    asyncio.run(history.add_message("user", [tool_result(identifier)]))


def assert_results_are_paired(messages):
    """Every tool_result must answer a tool_use in the message before it."""
    for index, message in enumerate(messages):
        for block in message["content"]:
            block_type = (
                block.get("type") if isinstance(block, dict) else block.type
            )
            if block_type != "tool_result":
                continue
            assert index > 0, "a tool_result opens the conversation"
            previous = messages[index - 1]["content"]
            calls = {
                (b.get("id") if isinstance(b, dict) else b.id)
                for b in previous
                if (b.get("type") if isinstance(b, dict) else b.type)
                == "tool_use"
            }
            assert block["tool_use_id"] in calls, (
                "tool_result survived without its tool_use"
            )


def test_keeps_the_only_tool_exchange_intact():
    # The reproduction from #520: one tool-using turn pushes the total over
    # the limit, so the opening user/assistant pair used to be removed and
    # the tool result sent alone.
    history = make_history(context_window_tokens=100)
    asyncio.run(history.add_message("user", "Use lookup"))
    add_tool_turn(history, "toolu_lookup", input_tokens=100)
    before = deepcopy(history.messages)

    history.truncate()

    assert history.messages == before
    assert_results_are_paired(history.format_for_api())


def test_removes_older_turns_but_not_the_last_exchange():
    history = make_history(context_window_tokens=100)
    asyncio.run(history.add_message("user", "Use lookup twice"))
    add_tool_turn(history, "toolu_1", input_tokens=100)
    add_tool_turn(history, "toolu_2", input_tokens=300)

    history.truncate()

    assert [m["role"] for m in history.messages] == [
        "user",
        "assistant",
        "user",
    ]
    assert (
        history.messages[0]["content"][0]["text"]
        == "[Earlier history has been truncated.]"
    )
    assert history.messages[1]["content"] == [tool_use("toolu_2")]
    assert history.messages[2]["content"] == [tool_result("toolu_2")]
    assert_results_are_paired(history.format_for_api())
    assert len(history.message_tokens) == 1


def test_can_still_drop_everything_before_a_plain_user_message():
    # A new user prompt needs no earlier message, so the old behavior of
    # clearing the whole history ahead of it is unchanged.
    history = make_history(context_window_tokens=100)
    asyncio.run(history.add_message("user", "First question"))
    asyncio.run(
        history.add_message(
            "assistant", "First answer", usage(input_tokens=100)
        )
    )
    asyncio.run(history.add_message("user", "Second question"))

    history.truncate()

    assert [m["role"] for m in history.messages] == ["user"]
    assert history.messages[0]["content"][0]["text"] == "Second question"


def test_no_change_under_the_limit():
    history = make_history(context_window_tokens=10_000)
    asyncio.run(history.add_message("user", "Use lookup"))
    add_tool_turn(history, "toolu_lookup", input_tokens=100)
    before = deepcopy(history.messages)

    history.truncate()

    assert history.messages == before


def test_agent_loop_sends_paired_tool_calls_under_a_tiny_window():
    class LookupTool(Tool):
        async def execute(self, key):
            return f"value for {key}"

    tool = LookupTool(
        name="lookup",
        description="Look up a key",
        input_schema={
            "type": "object",
            "properties": {"key": {"type": "string"}},
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
            content=(
                [
                    {
                        "type": "tool_use",
                        "id": "call_1",
                        "name": "lookup",
                        "input": {"key": "x"},
                    }
                ]
                if first
                else [{"type": "text", "text": "done"}]
            ),
            # the first turn alone exceeds the configured window below
            usage={
                "input_tokens": 500,
                "output_tokens": 10,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        )

    client = Mock()
    client.messages.count_tokens.return_value.input_tokens = 1
    client.messages.create.side_effect = create
    agent = Agent(
        "test",
        "test",
        tools=[tool],
        config=ModelConfig(context_window_tokens=100),
        client=client,
    )

    response = asyncio.run(agent.run_async("Look up x"))

    assert response.content[0].text == "done"
    assert len(requests) == 2
    assert_results_are_paired(requests[1]["messages"])
    assert requests[1]["messages"][-1]["content"][0]["tool_use_id"] == "call_1"
