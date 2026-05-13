"""Tests for the layout-independent typing path in ComputerTool.

We don't instantiate ComputerTool itself (its __init__ queries the real
screen); the `type` action is a thin wrapper around _type_text, which is what
we exercise here.
"""

import pytest

from computer_use.tools import computer


@pytest.fixture
def captured(monkeypatch):
    """Capture what _type_text would emit without touching the real keyboard."""
    unicode_chars: list[str] = []
    pressed_keys: list[str] = []

    # An event is just a token here; we record the unicode payload attached to
    # it and assert each token is actually posted.
    posted: list[object] = []
    monkeypatch.setattr(
        computer, "_CGEventCreateKeyboardEvent", lambda src, code, down: {"down": down}
    )
    monkeypatch.setattr(
        computer,
        "_CGEventKeyboardSetUnicodeString",
        lambda ev, _n, s: ev["down"] and unicode_chars.append(s),
    )
    monkeypatch.setattr(computer, "_CGEventPost", lambda _tap, ev: posted.append(ev))
    monkeypatch.setattr(computer.pyautogui, "press", pressed_keys.append)
    monkeypatch.setattr(
        computer.pyautogui,
        "write",
        lambda *a, **k: pytest.fail("pyautogui.write is layout-dependent; must not be called"),
    )
    monkeypatch.setattr(computer.time, "sleep", lambda _s: None)

    return {"unicode": unicode_chars, "pressed": pressed_keys, "posted": posted}


def test_type_text_uses_unicode_not_keycodes(captured):
    """Printable chars must go through CGEventKeyboardSetUnicodeString so the
    active keyboard layout (Dvorak, AZERTY, ...) cannot remap them."""
    computer._type_text("hello world")
    assert "".join(captured["unicode"]) == "hello world"
    assert captured["pressed"] == []
    # one keydown + one keyup posted per character
    assert len(captured["posted"]) == 2 * len("hello world")


def test_type_text_sends_real_keys_for_control_chars(captured):
    computer._type_text("a\n\tb")
    assert "".join(captured["unicode"]) == "ab"
    assert captured["pressed"] == ["enter", "tab"]


def test_type_text_handles_non_ascii(captured):
    """Bonus over pyautogui.write(): chars with no ANSI keycode at all."""
    computer._type_text("café — naïve")
    assert "".join(captured["unicode"]) == "café — naïve"


def test_hosted_param_reports_resized_dimensions(monkeypatch):
    """Tool params are built before any screenshot, so __init__ must compute
    the post-resize size up front rather than defaulting to raw screen size."""
    # 1512x982 is a common MacBook logical size; exceeds the token budget so
    # screenshots get downscaled.
    monkeypatch.setattr(computer.pyautogui, "size", lambda: (1512, 982))
    tool = computer.ComputerTool()
    p = tool.to_hosted_param()
    assert (p["display_width_px"], p["display_height_px"]) != (1512, 982)
    assert (p["display_width_px"], p["display_height_px"]) == (tool.sent_w, tool.sent_h)
    from computer_use.image import target_image_size

    assert (tool.sent_w, tool.sent_h) == target_image_size(1512, 982)


def test_hold_key_releases_on_interrupt(monkeypatch):
    """Ctrl+C during hold_key's sleep must still release the keys."""
    downs: list[str] = []
    ups: list[str] = []
    monkeypatch.setattr(computer.pyautogui, "size", lambda: (100, 100))
    monkeypatch.setattr(computer.pyautogui, "keyDown", downs.append)
    monkeypatch.setattr(computer.pyautogui, "keyUp", ups.append)

    def boom(_d):
        raise KeyboardInterrupt

    monkeypatch.setattr(computer.time, "sleep", boom)
    tool = computer.ComputerTool()
    with pytest.raises(KeyboardInterrupt):
        tool.execute(action="hold_key", text="shift+a", duration=5)
    assert downs == ["shift", "a"]
    assert ups == ["a", "shift"]
