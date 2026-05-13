from types import SimpleNamespace

import anthropic
import httpx
import pytest
from anthropic.types import ImageBlockParam, MessageParam

from computer_use.formatters import StripOldestImages
from computer_use.loop import (
    _call_with_retry,
    _format_usage,
    _is_empty_response,
    _is_recoverable,
)


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
        anthropic.APIConnectionError(request=httpx.Request("GET", "http://test"))
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
            raise anthropic.APIConnectionError(request=httpx.Request("GET", "http://test"))
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
