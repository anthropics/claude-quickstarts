"""
Full-screen computer control via pyautogui.

The model is shown a *resized* screenshot (see image.py). When it emits a
coordinate we scale it back to logical screen pixels using the dimensions of
the most recently sent screenshot. On retina displays pyautogui's screenshot
is in physical pixels while its mouse functions take logical pixels, so we
downscale to logical first.
"""

import contextlib
import subprocess
import time
from collections.abc import Iterator
from typing import Any, ClassVar, Literal

import pyautogui
import Quartz

from constants import HOSTED_COMPUTER_DATED_TYPE, HOSTED_COMPUTER_TOOLSET_TYPE

from ..image import ScreenshotTooSmall, resize_and_encode, target_image_size
from .base import Tool
from .result import ToolResult

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

# pyobjc bridges ObjC at runtime so Quartz attrs are invisible to pyright;
# bind the four we use once here rather than ignoring at every call site.
_CGEventCreateKeyboardEvent = Quartz.CGEventCreateKeyboardEvent  # pyright: ignore[reportAttributeAccessIssue]
_CGEventKeyboardSetUnicodeString = Quartz.CGEventKeyboardSetUnicodeString  # pyright: ignore[reportAttributeAccessIssue]
_CGEventPost = Quartz.CGEventPost  # pyright: ignore[reportAttributeAccessIssue]
_kCGHIDEventTap = Quartz.kCGHIDEventTap  # pyright: ignore[reportAttributeAccessIssue]

Action = Literal[
    "screenshot",
    "left_click",
    "double_click",
    "triple_click",
    "right_click",
    "middle_click",
    "mouse_move",
    "left_click_drag",
    "scroll",
    "type",
    "key",
    "hold_key",
    "left_mouse_down",
    "left_mouse_up",
    "cursor_position",
    "read_clipboard",
    "write_clipboard",
    "wait",
    "zoom",
]

# Upper bound of `key`'s repeat count; matches the hosted toolset's schema.
KEY_REPEAT_MAX = 100

# xdotool-style key names the model tends to emit -> pyautogui names.
# Anything not listed here passes through unchanged.
_KEY_ALIASES = {
    "control": "ctrl",
    "super": "command",
    "cmd": "command",
    "meta": "command",
    "return": "enter",
    "escape": "esc",
    "page_up": "pageup",
    "page_down": "pagedown",
    # On macOS pyautogui maps "delete" to Forward-Delete (kVK_ForwardDelete),
    # not the main Delete key (which is Backspace). Models almost always mean
    # Backspace when they say "delete", so remap it; expose the real
    # forward-delete under explicit aliases for the rare case it's wanted.
    "delete": "backspace",
    "del": "backspace",
    "forward_delete": "delete",
    "forwarddelete": "delete",
    # pyautogui's macOS map has no entry for the Windows-key names, so a
    # model emitting "win+r" out of cross-platform habit would silently no-op.
    "win": "command",
    "windows": "command",
    "winleft": "command",
    "winright": "command",
}


def _unmapped_keys(keys: list[str]) -> list[str]:
    """Return any keys that pyautogui's macOS backend has no keycode for."""
    from pyautogui._pyautogui_osx import keyboardMapping

    return [k for k in keys if keyboardMapping.get(k) is None]


def _translate_key(k: str) -> str:
    k = k.strip().lower()
    return _KEY_ALIASES.get(k, k)


def _modifiers(text: str | None) -> tuple[list[str], ToolResult | None]:
    """Parse the optional modifier chord a pointer action carries in `text`
    (e.g. "shift", "command+alt") into pyautogui key names, or an error result
    naming any key macOS has no keycode for."""
    mods = [_translate_key(k) for k in (text or "").split("+") if k]
    if bad := _unmapped_keys(mods):
        return mods, ToolResult(
            error=f"unsupported modifier key(s) on macOS: {bad}; no keycode exists"
        )
    return mods, None


@contextlib.contextmanager
def _held(mods: list[str]) -> Iterator[None]:
    """Hold `mods` down around a pointer action. Released in a finally so an
    exception (or Ctrl-C) mid-action can't leave a modifier stuck down on the
    user's real desktop."""
    for m in mods:
        pyautogui.keyDown(m)
    try:
        yield
    finally:
        for m in reversed(mods):
            pyautogui.keyUp(m)


# Characters that should be sent as real key events rather than unicode
# insertions, so apps that watch for the keydown (not just text input) react.
# Their keycodes (Return, Tab, Delete) are layout-stable so pyautogui is fine.
_KEYPRESS_CHARS = {"\n": "enter", "\r": "enter", "\t": "tab", "\b": "backspace"}


def _type_text(text: str, interval: float = 0.01) -> None:
    """Layout-independent typing.

    pyautogui.write() sends hardcoded ANSI virtual keycodes (physical key
    positions on a US QWERTY board), which macOS then re-translates through
    the *active* layout — so on Dvorak, AZERTY, etc. the wrong characters
    appear. We instead post each printable character as a Unicode string on a
    keyboard event via CGEventKeyboardSetUnicodeString; macOS inserts that
    string verbatim regardless of the current layout.
    """
    for ch in text:
        if key := _KEYPRESS_CHARS.get(ch):
            pyautogui.press(key)
        else:
            for key_down in (True, False):
                ev = _CGEventCreateKeyboardEvent(None, 0, key_down)
                _CGEventKeyboardSetUnicodeString(ev, len(ch), ch)
                _CGEventPost(_kCGHIDEventTap, ev)
        time.sleep(interval)


def _as_xy(coord: Any) -> list[int]:
    """Coerce a coordinate to ``[x, y]`` integers.

    Claude reliably emits arrays (``[500, 375]``), but weaker / non-Claude
    models routed through the same loop sometimes send a string instead
    (``"500,375"`` or ``"[500, 375]"``). Accept both so a single malformed
    coordinate degrades to a clear error rather than an opaque
    ``too many values to unpack`` from the bare ``x, y = coord`` unpack.
    """
    if isinstance(coord, str):
        parts = [p.strip() for p in coord.strip().strip("[]()").split(",") if p.strip()]
    elif isinstance(coord, (list, tuple)):
        parts = list(coord)
    else:
        raise ValueError(f"coordinate must be [x, y], got {type(coord).__name__}: {coord!r}")
    if len(parts) != 2:
        raise ValueError(f"coordinate must have exactly 2 values [x, y], got {coord!r}")
    try:
        return [round(float(parts[0])), round(float(parts[1]))]
    except (TypeError, ValueError):
        raise ValueError(f"coordinate values must be numbers, got {coord!r}")


class ComputerTool(Tool):
    name: ClassVar[str] = "computer"
    validates_own_input: ClassVar[bool] = True
    description: ClassVar[str] = (
        "Control the local macOS screen: take screenshots, move/click the mouse, "
        "type, press keys, scroll, and read/write the clipboard. Coordinates are "
        "pixels in the most recent screenshot, origin top-left."
    )
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": list(Action.__args__),
                "description": (
                    "* screenshot: capture the screen.\n"
                    "* left_click / double_click / triple_click / right_click / "
                    "middle_click: click at `coordinate` (or the current cursor "
                    "position if omitted); optional `text` holds modifier keys "
                    "(e.g. 'command') during the click.\n"
                    "* mouse_move: move cursor to `coordinate`.\n"
                    "* left_click_drag: drag from `start_coordinate` to `coordinate`; "
                    "optional `text` holds modifier keys during the drag.\n"
                    "* scroll: scroll at `coordinate` (or the current cursor position) "
                    "in `scroll_direction` by `scroll_amount` notches; optional `text` "
                    "holds modifier keys during the scroll.\n"
                    "* type: type literal `text` at the current focus.\n"
                    "* key: press a chord like 'ctrl+shift+t' or a single key, "
                    "`repeat` times (default once).\n"
                    "* hold_key: hold the chord in `text` for `duration` seconds.\n"
                    "* left_mouse_down / left_mouse_up: press or release the left "
                    "button at `coordinate` (or the current cursor position), for "
                    "manual drags or long-press.\n"
                    "* cursor_position: return the current cursor x,y.\n"
                    "* read_clipboard / write_clipboard: get/set clipboard `text`.\n"
                    "* wait: sleep `duration` seconds.\n"
                    "* zoom: return a cropped, higher-detail view of the screen "
                    "region `region` = [x1, y1, x2, y2]. Use this to read small "
                    "text or inspect fine detail. Coordinates in subsequent "
                    "actions still refer to the full screenshot, not the zoom."
                ),
            },
            "coordinate": {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 2,
                "maxItems": 2,
            },
            "start_coordinate": {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 2,
                "maxItems": 2,
            },
            "text": {"type": "string"},
            "repeat": {"type": "integer", "minimum": 1, "maximum": KEY_REPEAT_MAX},
            "scroll_direction": {"type": "string", "enum": ["up", "down", "left", "right"]},
            "scroll_amount": {"type": "integer", "minimum": 1},
            "duration": {"type": "number", "minimum": 0, "maximum": 60},
            "region": {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 4,
                "maxItems": 4,
                "description": "[x1, y1, x2, y2] in the same image space as `coordinate`.",
            },
        },
        "required": ["action"],
    }

    def __init__(self) -> None:
        self.screen_w, self.screen_h = pyautogui.size()
        # Tool params are built once before any screenshot, so compute the
        # post-resize dimensions now (target_image_size is deterministic given
        # the screen size and config) instead of waiting for take_screenshot()
        # to set them.
        self.sent_w, self.sent_h = target_image_size(self.screen_w, self.screen_h)

    def to_hosted_toolset_param(self) -> dict[str, Any]:
        """The server-hosted toolset declaration (first-party API). One nameless
        entry declares every action as a member tool; the server supplies all
        descriptions and schemas. It takes no display size -- coordinates are in
        screenshot pixels, which the screenshots themselves establish -- and
        member calls come back as tool_use blocks named after the action with
        toolset_name="computer" (routed by ToolCollection.run). Every member,
        including `zoom` (enabled by default in the toolset), is implemented
        below: the explicit action set is a superset of the toolset's."""
        return {"type": HOSTED_COMPUTER_TOOLSET_TYPE}

    def to_hosted_dated_param(self) -> dict[str, Any]:
        """The server-hosted dated single-tool declaration (Vertex/Bedrock).
        The server supplies the description and input_schema; we declare the
        type and the display size in screenshot pixels, since that is the
        coordinate space the model sees."""
        return {
            "type": HOSTED_COMPUTER_DATED_TYPE,
            "name": self.name,
            "display_width_px": int(self.sent_w),
            "display_height_px": int(self.sent_h),
        }

    def _scale_to_screen(self, coord: list[int]) -> tuple[int, int]:
        x, y = _as_xy(coord)
        sx = round(x * self.screen_w / self.sent_w)
        sy = round(y * self.screen_h / self.sent_h)
        return (
            max(0, min(sx, self.screen_w - 1)),
            max(0, min(sy, self.screen_h - 1)),
        )

    def _scale_to_image(self, screen_x: int, screen_y: int) -> tuple[int, int]:
        return (
            round(screen_x * self.sent_w / self.screen_w),
            round(screen_y * self.sent_h / self.screen_h),
        )

    def _at(self, image_coord: list[int]) -> str:
        """Format a coordinate for tool output. Echoes the *image-space* values
        the model sent (not the scaled screen pixels) so the model sees its own
        numbers back; the WxH suffix tells human readers which space this is."""
        x, y = _as_xy(image_coord)
        return f"({x}, {y}) in {self.sent_w}x{self.sent_h} image"

    def take_screenshot(self) -> ToolResult:
        img = pyautogui.screenshot()
        # Retina: physical-px screenshot, logical-px mouse space.
        if img.width != self.screen_w or img.height != self.screen_h:
            img = img.resize((self.screen_w, self.screen_h))

        try:
            b64, (self.sent_w, self.sent_h) = resize_and_encode(img)
        except ScreenshotTooSmall as e:
            return ToolResult(error=str(e))

        return ToolResult(
            base64_image=b64,
            meta={
                "sent_size": [self.sent_w, self.sent_h],
                "screen_size": [self.screen_w, self.screen_h],
            },
        )

    def execute(self, **kwargs: Any) -> ToolResult:
        action: Action = kwargs["action"]

        if action == "screenshot":
            return self.take_screenshot()

        # Pointer actions take an optional coordinate; omitted means "where the
        # cursor already is" (the hosted toolset's members are declared that way).
        coord: list[int] | None = kwargs.get("coordinate")
        where = f" at {self._at(coord)}" if coord is not None else " at the cursor"

        if action in {
            "left_click",
            "double_click",
            "triple_click",
            "right_click",
            "middle_click",
        }:
            button = {"right_click": "right", "middle_click": "middle"}.get(action, "left")
            clicks = {"double_click": 2, "triple_click": 3}.get(action, 1)
            mods, err = _modifiers(kwargs.get("text"))
            if err:
                return err
            if coord is not None:
                pyautogui.moveTo(*self._scale_to_screen(coord))
            with _held(mods):
                pyautogui.click(clicks=clicks, interval=0.05, button=button)
            return ToolResult(output=f"{action}{where}")

        if action in {"left_mouse_down", "left_mouse_up"}:
            if coord is not None:
                pyautogui.moveTo(*self._scale_to_screen(coord))
            if action == "left_mouse_down":
                pyautogui.mouseDown(button="left")
            else:
                pyautogui.mouseUp(button="left")
            return ToolResult(output=f"{action}{where}")

        if action == "mouse_move":
            if coord is None:
                return ToolResult(error="mouse_move requires `coordinate`")
            pyautogui.moveTo(*self._scale_to_screen(coord))
            return ToolResult(output=f"moved to {self._at(coord)}")

        if action == "left_click_drag":
            start = kwargs.get("start_coordinate")
            if start is None or coord is None:
                return ToolResult(
                    error="left_click_drag requires `start_coordinate` and `coordinate`"
                )
            mods, err = _modifiers(kwargs.get("text"))
            if err:
                return err
            pyautogui.moveTo(*self._scale_to_screen(start))
            with _held(mods):
                pyautogui.dragTo(*self._scale_to_screen(coord), duration=0.3, button="left")
            return ToolResult(output=f"dragged {self._at(start)} -> {self._at(coord)}")

        if action == "scroll":
            amount = kwargs.get("scroll_amount", 3)
            direction = kwargs["scroll_direction"]
            mods, err = _modifiers(kwargs.get("text"))
            if err:
                return err
            if coord is not None:
                pyautogui.moveTo(*self._scale_to_screen(coord))
            with _held(mods):
                if direction in {"up", "down"}:
                    pyautogui.scroll(amount if direction == "up" else -amount)
                else:
                    pyautogui.hscroll(amount if direction == "right" else -amount)
            return ToolResult(output=f"scrolled {direction} by {amount}{where}")

        if action == "type":
            _type_text(kwargs["text"], interval=0.01)
            return ToolResult(output=f"typed {len(kwargs['text'])} chars")

        if action == "key":
            keys = [_translate_key(k) for k in kwargs["text"].split("+")]
            if bad := _unmapped_keys(keys):
                return ToolResult(
                    error=(
                        f"unsupported key(s) on macOS: {bad}; pyautogui has no "
                        f"keycode for these. Use a macOS equivalent or omit them."
                    )
                )
            repeat = kwargs.get("repeat", 1)
            if not isinstance(repeat, int) or not 1 <= repeat <= KEY_REPEAT_MAX:
                return ToolResult(error=f"`repeat` must be an integer in 1..{KEY_REPEAT_MAX}")
            for _ in range(repeat):
                pyautogui.hotkey(*keys)
            times = f" x{repeat}" if repeat > 1 else ""
            return ToolResult(output=f"pressed {'+'.join(keys)}{times}")

        if action == "hold_key":
            keys = [_translate_key(k) for k in kwargs["text"].split("+")]
            if bad := _unmapped_keys(keys):
                return ToolResult(error=f"unsupported key(s) on macOS: {bad}; no keycode exists")
            d = min(max(kwargs.get("duration", 1.0), 0), 60)
            for k in keys:
                pyautogui.keyDown(k)
            try:
                time.sleep(d)
            finally:
                # Ctrl+C during the sleep would otherwise leave the keys held
                # at the OS level on the user's real desktop.
                for k in reversed(keys):
                    pyautogui.keyUp(k)
            return ToolResult(output=f"held {'+'.join(keys)} for {d}s")

        if action == "cursor_position":
            sx, sy = pyautogui.position()
            return ToolResult(output=f"cursor at {self._at(list(self._scale_to_image(sx, sy)))}")

        if action == "read_clipboard":
            out = subprocess.run(["pbpaste"], capture_output=True, text=True, check=True)
            return ToolResult(output=out.stdout)

        if action == "write_clipboard":
            subprocess.run(["pbcopy"], input=kwargs["text"], text=True, check=True)
            return ToolResult(output="clipboard set")

        if action == "wait":
            d = min(max(kwargs.get("duration", 1.0), 0), 60)
            time.sleep(d)
            return ToolResult(output=f"waited {d}s")

        if action == "zoom":
            return self._zoom(kwargs.get("region"))

        return ToolResult(error=f"unknown action: {action}")

    def _zoom(self, region: list[int] | None) -> ToolResult:
        if not region or len(region) != 4:
            return ToolResult(error="zoom requires `region` = [x1, y1, x2, y2]")
        x1, y1, x2, y2 = region
        if x2 <= x1 or y2 <= y1:
            return ToolResult(error="zoom region must have x2 > x1 and y2 > y1")
        # Capture at full physical resolution (retina) so the crop carries more
        # detail than the same area did in the downscaled full-screen shot.
        full = pyautogui.screenshot()
        fx, fy = full.width / self.sent_w, full.height / self.sent_h
        box = (
            max(0, round(x1 * fx)),
            max(0, round(y1 * fy)),
            min(full.width, round(x2 * fx)),
            min(full.height, round(y2 * fy)),
        )
        crop = full.crop(box)
        try:
            b64, (cw, ch) = resize_and_encode(crop, min_bytes=0)
        except ValueError as e:
            return ToolResult(error=str(e))
        return ToolResult(
            output=(
                f"zoom of ({x1},{y1})-({x2},{y2}) in {self.sent_w}x{self.sent_h} image, "
                f"shown at {cw}x{ch}. Subsequent coordinates still refer to the "
                f"full {self.sent_w}x{self.sent_h} screenshot, not this crop."
            ),
            base64_image=b64,
        )
