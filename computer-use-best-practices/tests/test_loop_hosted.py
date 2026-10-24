"""Drive sampling_loop end-to-end in hosted mode against a canned API.

Everything real except the network: the loop, ToolCollection routing, and
ComputerTool run as they would in production (pyautogui is monkeypatched so
nothing touches the desktop), and the assertions are on the request bodies the
SDK actually serialized -- the declaration sent, the beta header, and the
tool_result blocks answering a multi-member turn.
"""

import json
from typing import Any

import anthropic
import httpx2
import pytest

import constants
from computer_use import loop
from computer_use.tools import computer as computer_module
from computer_use.tools.base import ToolCollection
from computer_use.tools.computer import ComputerTool
from constants import TOOLSET_NOT_EXECUTED

MEMBER_TURN = [
    {"type": "tool_use", "id": "t1", "name": "left_click", "toolset_name": "computer",
     "input": {"coordinate": [5, 5]}},
    # mouse_move without a coordinate fails client-side...
    {"type": "tool_use", "id": "t2", "name": "mouse_move", "toolset_name": "computer", "input": {}},
    # ...so this member must be answered without running.
    {"type": "tool_use", "id": "t3", "name": "key", "toolset_name": "computer",
     "input": {"text": "enter", "repeat": 2}},
]  # fmt: skip

DATED_TURN = [
    {"type": "tool_use", "id": "t1", "name": "computer",
     "input": {"action": "left_click", "coordinate": [5, 5]}},
]  # fmt: skip


def _sse(content: list[dict[str, Any]], stop_reason: str) -> bytes:
    """Encode one assistant message the way the streaming endpoint would."""
    message = {
        "id": "msg", "type": "message", "role": "assistant", "model": "m", "content": [],
        "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1},
    }  # fmt: skip
    lines: list[str] = []

    def emit(name: str, **data: Any) -> None:
        lines.append(f"event: {name}\ndata: {json.dumps({'type': name, **data})}\n\n")

    emit("message_start", message=message)
    for i, block in enumerate(content):
        if block["type"] == "text":
            emit("content_block_start", index=i, content_block={"type": "text", "text": ""})
            delta: dict[str, Any] = {"type": "text_delta", "text": block["text"]}
        else:
            emit("content_block_start", index=i, content_block={**block, "input": {}})
            delta = {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}
        emit("content_block_delta", index=i, delta=delta)
        emit("content_block_stop", index=i)
    stop = {"stop_reason": stop_reason, "stop_sequence": None}
    emit("message_delta", delta=stop, usage={"output_tokens": 1})
    emit("message_stop")
    return "".join(lines).encode()


class _NullTrajectory:
    def record(self, role: str, content: Any) -> None:
        pass


@pytest.fixture
def gui_calls(monkeypatch):
    calls: list[str] = []
    for fn in ("moveTo", "click", "hotkey", "keyDown", "keyUp"):
        monkeypatch.setattr(
            computer_module.pyautogui, fn, lambda *a, _fn=fn, **k: calls.append(_fn)
        )
    monkeypatch.setattr(computer_module.pyautogui, "size", lambda: (1024, 768))
    return calls


def _run_loop(monkeypatch, *, provider: str, first_turn: list[dict[str, Any]]):
    """Run one task through the loop; return the captured (headers, body) per request."""
    requests: list[tuple[httpx2.Headers, dict[str, Any]]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append((request.headers, json.loads(request.content)))
        body = (
            _sse(first_turn, "tool_use")
            if len(requests) == 1
            else _sse([{"type": "text", "text": "done"}], "end_turn")
        )
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=body)

    client = anthropic.Anthropic(
        api_key="test", http_client=httpx2.Client(transport=httpx2.MockTransport(handler))
    )
    cfg = constants.cfg.with_overrides(
        provider=provider,
        use_hosted_computer_tool=True,
        enable_advisor_tool=False,
        enable_autocompaction=False,
        print_usage=False,
    )
    monkeypatch.setattr(loop, "cfg", cfg)
    monkeypatch.setattr(loop, "_make_client", lambda _provider: client)

    loop.sampling_loop(
        model="m",
        task="go",
        tools=ToolCollection(ComputerTool()),
        trajectory=_NullTrajectory(),  # type: ignore[arg-type]
        thinking_effort="off",
        interactive=False,
    )
    assert len(requests) == 2
    return requests


def test_toolset_mode_end_to_end(monkeypatch, gui_calls):
    (headers, first), (_, second) = _run_loop(
        monkeypatch, provider="anthropic", first_turn=MEMBER_TURN
    )

    assert first["tools"] == [{"type": "computer_toolset_20260801"}]
    assert "anthropic-beta" not in headers

    # The failed second member stopped the turn: t3 was answered, not executed.
    results = second["messages"][2]["content"]
    assert [(r["tool_use_id"], r["toolset_name"], r["is_error"]) for r in results] == [
        ("t1", "computer", False),
        ("t2", "computer", True),
        ("t3", "computer", True),
    ]
    assert results[2]["content"][0]["text"] == TOOLSET_NOT_EXECUTED
    assert gui_calls == ["moveTo", "click"]  # no hotkey: t3 never ran

    # The assistant turn is replayed with toolset_name intact on every block;
    # without it the API would treat these as unknown custom tools.
    replayed = second["messages"][1]["content"]
    assert [b["toolset_name"] for b in replayed] == ["computer"] * 3


def test_dated_fallback_end_to_end(monkeypatch, gui_calls):
    (headers, first), (_, second) = _run_loop(monkeypatch, provider="vertex", first_turn=DATED_TURN)

    (tool,) = first["tools"]
    assert tool["type"] == "computer_20250124" and tool["name"] == "computer"
    assert headers["anthropic-beta"] == "computer-use-2025-01-24"

    (result,) = second["messages"][2]["content"]
    assert result["tool_use_id"] == "t1" and not result["is_error"]
    assert "toolset_name" not in result
    assert gui_calls == ["moveTo", "click"]
