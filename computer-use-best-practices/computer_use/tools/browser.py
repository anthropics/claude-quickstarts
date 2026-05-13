"""
Headless browser tool backed by Playwright.

The viewport is fixed at 1456x819 (the documented 16:9 max size) so
screenshots already satisfy the vision-encoder budget and need no resize.
We still route them through resize_and_encode for uniform JPEG encoding.
"""

import io
import time
from typing import Any, ClassVar, Literal

from PIL import Image
from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from constants import cfg

from ..image import ScreenshotTooSmall, resize_and_encode
from .base import Tool
from .result import ToolResult

# Playwright's keyboard.press() uses Web KeyboardEvent.key names
# (https://developer.mozilla.org/docs/Web/API/KeyboardEvent/key/Key_Values),
# not the xdotool/pyautogui names models tend to emit. Normalize common ones.
# As with the computer tool, "delete" is mapped to Backspace because that's
# almost always what the model means by it.
_PLAYWRIGHT_KEY_ALIASES = {
    "ctrl": "Control",
    "control": "Control",
    "cmd": "Meta",
    "command": "Meta",
    "super": "Meta",
    "win": "Meta",
    "windows": "Meta",
    "meta": "Meta",
    "alt": "Alt",
    "option": "Alt",
    "shift": "Shift",
    "enter": "Enter",
    "return": "Enter",
    "esc": "Escape",
    "escape": "Escape",
    "tab": "Tab",
    "space": "Space",
    "backspace": "Backspace",
    "delete": "Backspace",
    "del": "Backspace",
    "forward_delete": "Delete",
    "forwarddelete": "Delete",
    "up": "ArrowUp",
    "down": "ArrowDown",
    "left": "ArrowLeft",
    "right": "ArrowRight",
    "pageup": "PageUp",
    "page_up": "PageUp",
    "pagedown": "PageDown",
    "page_down": "PageDown",
    "home": "Home",
    "end": "End",
}


def _to_playwright_chord(text: str) -> str:
    """Normalize a model-emitted chord like 'ctrl+shift+a' to Playwright's
    'Control+Shift+a'. Unknown segments pass through unchanged."""
    parts = [p.strip() for p in text.split("+") if p.strip()]
    return "+".join(_PLAYWRIGHT_KEY_ALIASES.get(p.lower(), p) for p in parts)


_ACTIONS = [
    "navigate",
    "screenshot",
    "left_click",
    "right_click",
    "middle_click",
    "double_click",
    "triple_click",
    "scroll",
    "type",
    "key",
    "get_page_text",
    "find",
    "execute_js",
    "wait",
    "zoom",
]


class BrowserTool(Tool):
    name: ClassVar[str] = "browser"
    validates_own_input: ClassVar[bool] = True
    description: ClassVar[str] = (
        "Drive a headless Chromium browser. Use `navigate` first; subsequent "
        "actions operate on the current page. Coordinates are viewport pixels "
        f"({cfg.browser_viewport[0]}x{cfg.browser_viewport[1]}, origin top-left)."
    )
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": _ACTIONS},
            "url": {"type": "string", "description": "for navigate"},
            "coordinate": {"type": "array", "items": {"type": "integer"}},
            "text": {
                "type": "string",
                "description": "for type/key/find/execute_js",
            },
            "scroll_direction": {"type": "string", "enum": ["up", "down", "left", "right"]},
            "scroll_amount": {"type": "integer"},
            "duration": {"type": "number", "minimum": 0, "maximum": 60},
            "region": {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 4,
                "maxItems": 4,
                "description": "[x1, y1, x2, y2] viewport pixels for the zoom action.",
            },
        },
        "required": ["action"],
    }

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._page: Page | None = None

    def _ensure_page(self) -> Page:
        # Each step is guarded separately so a failure partway through (most
        # commonly chromium.launch when the browser binary isn't installed)
        # doesn't restart Playwright on the next call; sync_playwright cannot
        # be started twice in one process.
        if self._playwright is None:
            self._playwright = sync_playwright().start()
        if self._browser is None:
            self._browser = self._playwright.chromium.launch(headless=True)
        if self._page is None:
            ctx = self._browser.new_context(
                viewport={"width": cfg.browser_viewport[0], "height": cfg.browser_viewport[1]}
            )
            self._page = ctx.new_page()
        return self._page

    def _screenshot(self, page: Page, output: str | None = None) -> ToolResult:
        png = page.screenshot()
        try:
            b64, _ = resize_and_encode(Image.open(io.BytesIO(png)))
        except ScreenshotTooSmall as e:
            return ToolResult(error=str(e))
        return ToolResult(output=output, base64_image=b64)

    def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs["action"]
        try:
            page = self._ensure_page()
        except Exception as e:
            if "executable doesn't exist" in str(e).lower():
                return ToolResult(
                    error=(
                        "The Playwright Chromium browser is not installed on this "
                        "machine. Tell the user to run "
                        "`uv run playwright install chromium` and then retry."
                    )
                )
            raise

        if action == "navigate":
            page.goto(kwargs["url"], wait_until="domcontentloaded")
            return self._screenshot(page, output=f"navigated to {page.url}")

        if action == "screenshot":
            return self._screenshot(page)

        if action in {"left_click", "right_click", "middle_click", "double_click", "triple_click"}:
            x, y = kwargs["coordinate"]
            buttons: dict[str, Literal["left", "middle", "right"]] = {
                "right_click": "right",
                "middle_click": "middle",
            }
            counts: dict[str, int] = {"double_click": 2, "triple_click": 3}
            page.mouse.click(
                x, y, button=buttons.get(action, "left"), click_count=counts.get(action, 1)
            )
            return ToolResult(
                output=f"{action} at ({x}, {y}) in {cfg.browser_viewport[0]}x{cfg.browser_viewport[1]} image"
            )

        if action == "scroll":
            x, y = kwargs["coordinate"]
            pixels = kwargs.get("scroll_amount", 3) * 100
            direction = kwargs["scroll_direction"]
            dx = pixels if direction == "right" else -pixels if direction == "left" else 0
            dy = pixels if direction == "down" else -pixels if direction == "up" else 0
            page.mouse.move(x, y)
            page.mouse.wheel(dx, dy)
            return ToolResult(
                output=(
                    f"scrolled {direction} at ({x}, {y}) in "
                    f"{cfg.browser_viewport[0]}x{cfg.browser_viewport[1]} image"
                )
            )

        if action == "type":
            page.keyboard.type(kwargs["text"])
            return ToolResult(output=f"typed {len(kwargs['text'])} chars")

        if action == "key":
            chord = _to_playwright_chord(kwargs["text"])
            page.keyboard.press(chord)
            return ToolResult(output=f"pressed {chord}")

        if action == "get_page_text":
            text = page.inner_text("body")
            return ToolResult(output=text)

        if action == "find":
            needle = kwargs["text"]
            count = page.evaluate("(n) => document.body.innerText.split(n).length - 1", needle)
            return ToolResult(output=f"found {count} occurrence(s) of {needle!r}")

        if action == "execute_js":
            result = page.evaluate(kwargs["text"])
            return ToolResult(output=repr(result))

        if action == "wait":
            d = min(max(kwargs.get("duration", 1.0), 0), 60)
            time.sleep(d)
            return ToolResult(output=f"waited {d}s")

        if action == "zoom":
            region = kwargs.get("region")
            if not region or len(region) != 4:
                return ToolResult(error="zoom requires `region` = [x1, y1, x2, y2]")
            x1, y1, x2, y2 = region
            if x2 <= x1 or y2 <= y1:
                return ToolResult(error="zoom region must have x2 > x1 and y2 > y1")
            png = page.screenshot(clip={"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1})
            b64, (cw, ch) = resize_and_encode(Image.open(io.BytesIO(png)), min_bytes=0)
            return ToolResult(
                output=(
                    f"zoom of ({x1},{y1})-({x2},{y2}) in "
                    f"{cfg.browser_viewport[0]}x{cfg.browser_viewport[1]} image, shown at {cw}x{ch}. "
                    f"Subsequent coordinates still refer to the full viewport, not this crop."
                ),
                base64_image=b64,
            )

        return ToolResult(error=f"unknown action: {action}")

    def close(self) -> None:
        try:
            if self._browser:
                try:
                    self._browser.close()
                finally:
                    self._browser = None
                    self._page = None
        finally:
            if self._playwright:
                try:
                    self._playwright.stop()
                finally:
                    self._playwright = None
