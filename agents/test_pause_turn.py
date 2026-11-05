#!/usr/bin/env python3
"""Offline tests for pause_turn continuation in the agent loop.

A server-tool response (web search / code execution) with
stop_reason="pause_turn" carries only server_tool_use blocks, so it has
no client tool calls. run() must continue the turn instead of returning
the unfinished response, and must bound consecutive continuations.

These tests use a mocked client and real SDK Message objects; they make
no API calls. The two continuation/bound tests disable prompt caching
to isolate stop-reason handling; a third test covers the shipped
default configuration (caching enabled), where the continued assistant
message is the last history entry and goes through format_for_api's
cache-control formatting.
"""

import os
import sys
from unittest.mock import Mock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from anthropic.types import Message, StopReason, Usage

from agents.agent import MAX_PAUSE_TURN_CONTINUATIONS, Agent
from agents.tools.web_search import WebSearchServerTool


def _response(stop_reason: StopReason, content: list) -> Message:
    return Message(
        id="msg_test",
        type="message",
        role="assistant",
        model="claude-sonnet-5-5",
        stop_reason=stop_reason,
        content=content,
        usage=Usage(
            input_tokens=20,
            output_tokens=10,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        ),
    )


def _paused_response() -> Message:
    return _response(
        "pause_turn",
        [
            {
                "type": "server_tool_use",
                "id": "srvtoolu_test",
                "name": "web_search",
                "input": {"query": "test query"},
            }
        ],
    )


def _agent_with_client(client: Mock, enable_caching: bool = False) -> Agent:
    agent = Agent(
        name="test",
        system="test",
        tools=[WebSearchServerTool()],
        client=client,
    )
    # The default is False here to isolate stop-reason handling from
    # prompt-cache formatting of SDK content blocks; the default-config
    # test below passes True (the MessageHistory default).
    agent.history.enable_caching = enable_caching
    return agent


def _mock_client() -> Mock:
    client = Mock()
    client.messages.count_tokens.return_value = Mock(input_tokens=1)
    return client


def test_pause_turn_continues_and_returns_final_response() -> None:
    paused = _paused_response()
    finished = _response("end_turn", [{"type": "text", "text": "Finished answer"}])
    client = _mock_client()
    client.messages.create.side_effect = [paused, finished]

    result = _agent_with_client(client).run("Please search and answer")

    assert result is finished
    assert client.messages.create.call_count == 2


def test_pause_turn_continues_with_caching_enabled_default() -> None:
    paused = _paused_response()
    finished = _response("end_turn", [{"type": "text", "text": "Finished answer"}])
    client = _mock_client()
    client.messages.create.side_effect = [paused, finished]

    agent = _agent_with_client(client, enable_caching=True)
    # This is the configuration the example ships with: MessageHistory
    # defaults enable_caching to True and Agent never overrides it.
    assert agent.history.enable_caching is True

    result = agent.run("Please search and answer")

    assert result is finished
    assert client.messages.create.call_count == 2

    # The follow-up request carries the paused assistant message as its
    # last message: the SDK block dumped to a dict (the fields the API
    # sent, nothing more) with cache_control added by the caching
    # branch of format_for_api.
    follow_up_messages = client.messages.create.call_args_list[1].kwargs["messages"]
    assert follow_up_messages[-1] == {
        "role": "assistant",
        "content": [
            {
                "type": "server_tool_use",
                "id": "srvtoolu_test",
                "name": "web_search",
                "input": {"query": "test query"},
                "cache_control": {"type": "ephemeral"},
            }
        ],
    }


def test_pause_turn_bound_stops_the_loop() -> None:
    client = _mock_client()
    client.messages.create.side_effect = lambda **kwargs: _paused_response()

    result = _agent_with_client(client).run("Please search and answer")

    # The loop gives up gracefully: it returns the last (still paused)
    # response after the initial call plus the capped continuations.
    assert result.stop_reason == "pause_turn"
    assert client.messages.create.call_count == 1 + MAX_PAUSE_TURN_CONTINUATIONS
