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


def test_hosted_dated_param_reports_resized_dimensions(monkeypatch):
    """Tool params are built before any screenshot, so __init__ must compute
    the post-resize size up front rather than defaulting to raw screen size."""
    # 1512x982 is a common MacBook logical size; exceeds the token budget so
    # screenshots get downscaled.
    monkeypatch.setattr(computer.pyautogui, "size", lambda: (1512, 982))
    tool = computer.ComputerTool()
    p = tool.to_hosted_dated_param()
    assert (p["display_width_px"], p["display_height_px"]) != (1512, 982)
    assert (p["display_width_px"], p["display_height_px"]) == (tool.sent_w, tool.sent_h)
    from computer_use.image import target_image_size

    assert (tool.sent_w, tool.sent_h) == target_image_size(1512, 982)


@pytest.fixture
def gui(monkeypatch):
    """Record every pyautogui call the tool makes, in order, without touching
    the real desktop."""
    calls: list[tuple[str, tuple, dict]] = []
    for fn in (
        "moveTo",
        "click",
        "dragTo",
        "scroll",
        "hscroll",
        "keyDown",
        "keyUp",
        "hotkey",
        "mouseDown",
        "mouseUp",
    ):
        monkeypatch.setattr(
            computer.pyautogui, fn, lambda *a, _fn=fn, **k: calls.append((_fn, a, k))
        )
    monkeypatch.setattr(computer.pyautogui, "size", lambda: (1024, 768))
    return calls


def _names(calls):
    return [c[0] for c in calls]


def test_click_without_coordinate_clicks_where_the_cursor_is(gui):
    """Toolset members declare `coordinate` optional; the dated hosted schema
    and the explicit schema follow the same convention."""
    res = computer.ComputerTool().execute(action="left_click")
    assert not res.is_error
    assert _names(gui) == ["click"]
    assert "at the cursor" in (res.output or "")


def test_click_with_coordinate_moves_first(gui):
    computer.ComputerTool().execute(action="right_click", coordinate=[10, 20])
    assert _names(gui) == ["moveTo", "click"]
    assert gui[1][2]["button"] == "right"


def test_click_holds_modifiers_around_the_click(gui):
    computer.ComputerTool().execute(action="left_click", coordinate=[1, 1], text="shift+command")
    assert _names(gui) == ["moveTo", "keyDown", "keyDown", "click", "keyUp", "keyUp"]
    assert [c[1][0] for c in gui if c[0] == "keyDown"] == ["shift", "command"]
    assert [c[1][0] for c in gui if c[0] == "keyUp"] == ["command", "shift"]


def test_drag_and_scroll_accept_modifiers(gui):
    tool = computer.ComputerTool()
    tool.execute(action="left_click_drag", start_coordinate=[0, 0], coordinate=[5, 5], text="alt")
    assert _names(gui) == ["moveTo", "keyDown", "dragTo", "keyUp"]
    gui.clear()
    tool.execute(action="scroll", scroll_direction="down", scroll_amount=2, text="shift")
    assert _names(gui) == ["keyDown", "scroll", "keyUp"]
    assert gui[1][1] == (-2,)


def test_unmapped_modifier_is_an_error_before_any_input(gui):
    res = computer.ComputerTool().execute(action="left_click", coordinate=[1, 1], text="insert")
    assert res.is_error and "insert" in (res.error or "")
    assert gui == []


def test_mouse_down_up_without_coordinate_stay_put(gui):
    tool = computer.ComputerTool()
    tool.execute(action="left_mouse_down")
    tool.execute(action="left_mouse_up", coordinate=[3, 4])
    assert _names(gui) == ["mouseDown", "moveTo", "mouseUp"]


def test_actions_that_need_a_coordinate_say_so(gui):
    tool = computer.ComputerTool()
    assert "coordinate" in (tool.execute(action="mouse_move").error or "")
    assert "start_coordinate" in (
        tool.execute(action="left_click_drag", coordinate=[1, 1]).error or ""
    )
    assert gui == []


def test_key_repeat(gui):
    res = computer.ComputerTool().execute(action="key", text="ctrl+t", repeat=3)
    assert _names(gui) == ["hotkey"] * 3
    assert gui[0][1] == ("ctrl", "t")
    assert res.output == "pressed ctrl+t x3"


def test_key_defaults_to_a_single_press(gui):
    res = computer.ComputerTool().execute(action="key", text="enter")
    assert _names(gui) == ["hotkey"]
    assert res.output == "pressed enter"


@pytest.mark.parametrize("repeat", [0, 101, "3", 2.0])
def test_key_repeat_out_of_range_is_an_error(gui, repeat):
    res = computer.ComputerTool().execute(action="key", text="a", repeat=repeat)
    assert res.is_error and "repeat" in (res.error or "")
    assert gui == []


def test_explicit_schema_declares_repeat_within_the_toolset_bounds():
    prop = computer.ComputerTool.input_schema["properties"]["repeat"]
    assert (prop["minimum"], prop["maximum"]) == (1, computer.KEY_REPEAT_MAX) == (1, 100)


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


@pytest.mark.parametrize(
    "raw,expected",
    [
        ([500, 375], [500, 375]),
        ((500, 375), [500, 375]),
        ("500,375", [500, 375]),
        ("500, 375", [500, 375]),
        ("[500, 375]", [500, 375]),
        ("(500, 375)", [500, 375]),
        ([500.4, 375.6], [500, 376]),
    ],
)
def test_as_xy_accepts_lists_tuples_and_strings(raw, expected):
    """Claude emits arrays, but weaker / non-Claude models routed through the
    same loop sometimes send a coordinate as a string. Accept both."""
    assert computer._as_xy(raw) == expected


@pytest.mark.parametrize("bad", ["500,375,9", "abc", "", 5, [1], [1, 2, 3]])
def test_as_xy_rejects_malformed(bad):
    """A malformed coordinate must raise a clear ValueError, not the opaque
    'too many values to unpack' from a bare ``x, y = coord`` unpack."""
    with pytest.raises(ValueError):
        computer._as_xy(bad)
