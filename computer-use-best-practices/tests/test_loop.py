from types import SimpleNamespace
from typing import Any, ClassVar

import anthropic
import httpx2
import pytest
from anthropic.types import ImageBlockParam, MessageParam

from computer_use.formatters import StripOldestImages
from computer_use.loop import (
    _call_with_retry,
    _execute_tool_uses,
    _format_usage,
    _interrupted_result,
    _is_empty_response,
    _is_recoverable,
    _should_nudge_batch,
    _tool_result_block,
)
from computer_use.tools.base import Tool, ToolCollection
from computer_use.tools.result import ToolResult
from constants import TOOLSET_NOT_EXECUTED


def _img() -> ImageBlockParam:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": "x"},
    }


def test_prune_keeps_last_n():
    msgs: list[MessageParam] = [
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "1", "content": [_img()]},
                {"type": "tool_result", "tool_use_id": "2", "content": [_img(), _img()]},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "3", "content": [_img()]},
            ],
        },
    ]
    StripOldestImages(keep=2)(msgs)
    from computer_use.formatters import _image_slots

    assert len(_image_slots(msgs)) == 2


def test_format_usage_with_cache():
    u = SimpleNamespace(
        input_tokens=100,
        output_tokens=50,
        cache_read_input_tokens=900,
        cache_creation_input_tokens=20,
    )
    line = _format_usage(u, elapsed=1.234)
    assert "in=100" in line
    assert "cache_read=900" in line
    assert "cache_write=20" in line
    assert "out=50" in line
    assert "cache_eff=90%" in line
    assert "1.2s" in line


def test_format_usage_missing_cache_fields():
    u = SimpleNamespace(input_tokens=10, output_tokens=5)
    line = _format_usage(u, elapsed=0.0)
    assert "cache_read=0" in line and "cache_eff=0%" in line


def test_is_recoverable_classification():
    assert _is_recoverable(
        anthropic.APIConnectionError(request=httpx2.Request("GET", "http://test"))
    )
    assert _is_recoverable(Exception("Service overloaded, try again"))
    assert not _is_recoverable(ValueError("nope"))


def test_call_with_retry_recovers(monkeypatch):
    import computer_use.loop as loop_mod
    import constants

    fast = constants.cfg.with_overrides(api_retry_base_delay=0.0)
    monkeypatch.setattr(constants, "cfg", fast)
    monkeypatch.setattr(loop_mod, "cfg", fast)
    monkeypatch.setattr("time.sleep", lambda s: None)
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise anthropic.APIConnectionError(request=httpx2.Request("GET", "http://test"))
        return "ok"

    assert _call_with_retry(fn) == "ok"
    assert calls["n"] == 3


def test_call_with_retry_reraises_unrecoverable(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)

    def fn():
        # ValueError is neither in the recoverable nor unrecoverable list,
        # and "overloaded" not in message → re-raised on first attempt.
        raise ValueError("bad")

    with pytest.raises(ValueError):
        _call_with_retry(fn)


def test_is_empty_response():
    assert _is_empty_response([])
    assert _is_empty_response([SimpleNamespace(text="")])
    assert not _is_empty_response([SimpleNamespace(text="hi")])


def test_effort_kwargs():
    from computer_use.loop import _effort_kwargs

    assert _effort_kwargs("claude-sonnet-4-6", "off") == {"thinking": {"type": "disabled"}}
    assert _effort_kwargs("claude-sonnet-4-6", "low") == {"output_config": {"effort": "low"}}
    assert _effort_kwargs("claude-sonnet-4-6", "high") == {"output_config": {"effort": "high"}}


def test_thinking_effort_defaults_cover_all_models():
    from constants import Model, cfg

    assert set(cfg.thinking_effort) == set(Model)


def test_effort_unsupported_model_raises() -> None:
    import pytest

    from computer_use.loop import _effort_kwargs

    with pytest.raises(ValueError, match=r"does not support output_config\.effort"):
        _effort_kwargs("claude-haiku-4-5", "medium")
    assert _effort_kwargs("claude-haiku-4-5", "off") == {"thinking": {"type": "disabled"}}


class _Recorder(Tool):
    """Fails any call whose action is "boom"; records what reached execute()."""

    description = "test double"
    input_schema: ClassVar[dict[str, Any]] = {"type": "object", "properties": {}}
    validates_own_input = True
    calls: ClassVar[list[tuple[str, str]]] = []

    def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "?")
        _Recorder.calls.append((self.name, action))
        return ToolResult(error="boom") if action == "boom" else ToolResult(output="ok")


class _Computer(_Recorder):
    name = "computer"


class _Browser(_Recorder):
    name = "browser"


@pytest.fixture
def tools():
    _Recorder.calls.clear()
    return ToolCollection(_Computer(), _Browser())


def _member(name: str, id_: str = "toolu") -> SimpleNamespace:
    # What the SDK hands back for a hosted-toolset member call: the action is
    # the tool name, the family rides in toolset_name, the input has no action.
    return SimpleNamespace(id=id_, name=name, toolset_name="computer", input={})


def _plain(name: str, action: str, id_: str = "toolu") -> SimpleNamespace:
    return SimpleNamespace(id=id_, name=name, input={"action": action})


def test_execute_runs_members_in_order_and_stops_after_the_first_failure(tools):
    uses = [_member("left_click", "1"), _member("boom", "2"), _member("type", "3")]

    out = list(_execute_tool_uses(tools, uses))

    assert [(tu.id, res.is_error) for tu, res in out] == [("1", False), ("2", True), ("3", True)]
    assert out[2][1].error == TOOLSET_NOT_EXECUTED
    # The third member was answered without being run.
    assert _Recorder.calls == [("computer", "left_click"), ("computer", "boom")]


def test_execute_member_failure_does_not_stop_ordinary_tools(tools):
    uses = [_member("boom", "1"), _plain("browser", "navigate", "2"), _member("key", "3")]

    out = list(_execute_tool_uses(tools, uses))

    assert [res.is_error for _, res in out] == [True, False, True]
    assert _Recorder.calls == [("computer", "boom"), ("browser", "navigate")]


def test_execute_ordinary_failures_do_not_trip_the_member_short_circuit(tools):
    uses = [_plain("computer", "boom", "1"), _member("screenshot", "2")]

    out = list(_execute_tool_uses(tools, uses))

    assert [res.is_error for _, res in out] == [True, False]
    assert _Recorder.calls == [("computer", "boom"), ("computer", "screenshot")]


def test_tool_result_block_stamps_toolset_name_only_on_member_results():
    member = _tool_result_block(_member("zoom", "m"), [], is_error=False)
    plain = _tool_result_block(_plain("computer", "zoom", "p"), [], is_error=False)

    assert member["toolset_name"] == "computer" and member["tool_use_id"] == "m"  # type: ignore[typeddict-item]
    assert "toolset_name" not in plain and plain["tool_use_id"] == "p"


def test_interrupted_result_keeps_member_results_api_valid():
    block = _interrupted_result(_member("wait"))
    assert block["is_error"] is True and block["toolset_name"] == "computer"  # type: ignore[typeddict-item]
    assert "toolset_name" not in _interrupted_result(_plain("bash", "run"))


def test_batch_nudge_treats_a_lone_member_call_like_a_lone_action():
    assert _should_nudge_batch([_plain("computer", "left_click")])
    assert _should_nudge_batch([_member("left_click")])
    assert not _should_nudge_batch([_member("screenshot")])
    assert not _should_nudge_batch([_member("left_click"), _member("type")])
    assert not _should_nudge_batch([_plain("computer_batch", "left_click")])
