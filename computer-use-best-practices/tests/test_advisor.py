from types import SimpleNamespace

from computer_use.loop import (
    _advisor_tool_param,
    _format_usage,
    _strip_advisor,
)


def _stu(name: str = "advisor") -> SimpleNamespace:
    """A server_tool_use block as the SDK would return it (an object, not a dict)."""
    return SimpleNamespace(type="server_tool_use", id="x", name=name, input={})


def _atr(text: str = "plan") -> dict:
    return {
        "type": "advisor_tool_result",
        "tool_use_id": "x",
        "content": {"type": "advisor_result", "text": text},
    }


def test_advisor_tool_param_shape() -> None:
    p = _advisor_tool_param()
    assert p["type"] == "advisor_20260301"
    assert p["name"] == "advisor"
    assert isinstance(p["model"], str)
    caching = p.get("caching")
    assert caching is not None and caching["type"] == "ephemeral"


def test_strip_advisor_removes_blocks() -> None:
    messages = [
        {"role": "assistant", "content": [_stu(), _atr(), {"type": "text", "text": "ok"}]},
        {"role": "user", "content": "next"},
    ]
    _strip_advisor(messages)
    assert messages[0]["content"] == [{"type": "text", "text": "ok"}]
    assert messages[1]["content"] == "next"


def test_format_usage_with_advisor_iterations() -> None:
    usage = SimpleNamespace(
        input_tokens=100,
        output_tokens=50,
        cache_read_input_tokens=900,
        cache_creation_input_tokens=0,
        iterations=[
            SimpleNamespace(type="message", input_tokens=100, output_tokens=10),
            SimpleNamespace(
                type="advisor_message",
                model="claude-opus-4-6",
                input_tokens=800,
                cache_read_input_tokens=0,
                output_tokens=1500,
            ),
            SimpleNamespace(type="message", input_tokens=1400, output_tokens=40),
        ],
    )
    out = _format_usage(usage, 12.3)
    assert "advisor(claude-opus-4-6)" in out
    assert "in=800" in out
    assert "out=1500" in out
    assert out.count("\n") == 1  # one executor line + one advisor line


def test_autocompaction_edit_shape() -> None:
    from computer_use.loop import _autocompaction_edit

    e = _autocompaction_edit()
    assert e["type"] == "compact_20260112"
    assert e.get("trigger") == {"type": "input_tokens", "value": 150_000}
    assert "instructions" not in e


def test_advisor_reminder_interval_on_config() -> None:
    from constants import Config

    assert Config().advisor_reminder_interval == 20


def test_advisor_prompt_addendum_gated() -> None:
    import pytest

    import constants
    from computer_use import __main__ as cli

    mp = pytest.MonkeyPatch()
    try:
        off = constants.cfg.with_overrides(enable_advisor_tool=False)
        mp.setattr(constants, "cfg", off)
        mp.setattr(cli, "cfg", off)
        assert "advisor" not in cli.build_system_prompt(None).lower()
        on = constants.cfg.with_overrides(enable_advisor_tool=True)
        mp.setattr(constants, "cfg", on)
        mp.setattr(cli, "cfg", on)
        assert "advisor" in cli.build_system_prompt(None).lower()
    finally:
        mp.undo()
