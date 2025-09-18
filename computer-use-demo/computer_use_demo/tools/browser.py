"""Browser tool for web automation."""

import asyncio
import base64
import os
import shlex
from pathlib import Path
from typing import Literal, TypedDict, cast
from uuid import uuid4

from anthropic.types.beta import BetaToolUnionParam

from .base import BaseAnthropicTool, ToolError, ToolResult
from .run import run

OUTPUT_DIR = "/tmp/outputs"

BrowserAction = Literal[
    "navigate",
    "screenshot",
    "left_click",
    "right_click",
    "middle_click",
    "double_click",
    "triple_click",
    "left_click_drag",
    "left_mouse_down",
    "left_mouse_up",
    "scroll",
    "scroll_to",
    "type",
    "key",
    "hold_key",
    "read_page",
    "find",
    "get_page_text",
    "wait",
    "form_input",
    "javascript_exec",
    "zoom",
    "close_browser",
]

ScrollDirection = Literal["up", "down", "left", "right"]


class BrowserOptions(TypedDict):
    display_height_px: int
    display_width_px: int
    display_number: int | None


class BaseBrowserTool:
    """
    A tool that allows the agent to interact with a web browser.
    The tool parameters are defined by Anthropic and are not editable.
    """

    name: Literal["browser"] = "browser"
    width: int
    height: int
    display_num: int | None

    _screenshot_delay = 1.0

    @property
    def options(self) -> BrowserOptions:
        return {
            "display_width_px": self.width,
            "display_height_px": self.height,
            "display_number": self.display_num,
        }

    def __init__(self):
        super().__init__()

        self.width = int(os.getenv("WIDTH") or 1024)
        self.height = int(os.getenv("HEIGHT") or 768)

        if (display_num := os.getenv("DISPLAY_NUM")) is not None:
            self.display_num = int(display_num)
            self._display_prefix = f"DISPLAY=:{self.display_num} "
        else:
            self.display_num = None
            self._display_prefix = ""

        self.xdotool = f"{self._display_prefix}xdotool"

    async def ensure_browser_running(self) -> bool:
        """Check if Firefox is running and launch it if not."""
        # Check if Firefox process is running
        _, stdout, _ = await run("pgrep -f firefox")
        if stdout.strip():
            return True

        # Firefox not running - launch it in background with proper display
        launch_cmd = (
            f"DISPLAY=:{self.display_num} firefox > /dev/null 2>&1 &"
            if self.display_num
            else "firefox > /dev/null 2>&1 &"
        )
        await run(launch_cmd)
        await asyncio.sleep(5)  # Wait longer for Firefox to start

        # Verify it started
        _, stdout, _ = await run("pgrep -f firefox")
        return bool(stdout.strip())

    async def close_browser(self) -> ToolResult:
        """Gracefully close Firefox browser."""
        # Check if Firefox is running
        _, stdout, _ = await run("pgrep firefox")
        if not stdout.strip():
            return ToolResult(output="Firefox is not running")

        # Try graceful close first using xdotool to send Alt+F4
        await run(
            f"{self._display_prefix}xdotool search --class firefox windowactivate key alt+F4"
        )
        await asyncio.sleep(1)

        # Check if it closed
        _, stdout, _ = await run("pgrep firefox")
        if not stdout.strip():
            return ToolResult(output="Firefox closed successfully")

        # If still running, force kill
        await run("pkill -9 firefox")
        await asyncio.sleep(0.5)

        return ToolResult(output="Firefox force-closed")

    async def screenshot(self):
        """Take a screenshot of the current browser window."""
        output_dir = Path(OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"screenshot_{uuid4().hex}.png"

        screenshot_cmd = f"{self._display_prefix}scrot -p {path}"
        _, stdout, stderr = await run(screenshot_cmd)

        if path.exists():
            # Read the image file and encode to base64
            image_base64 = base64.b64encode(path.read_bytes()).decode()
            # Don't include stdout in the result - scrot might output to stdout
            return ToolResult(
                output="",  # Clear output to avoid contamination
                error=stderr if stderr else None,
                base64_image=image_base64,
            )
        raise ToolError(f"Failed to take screenshot: {stderr}")

    async def shell(self, command: str, take_screenshot=True) -> ToolResult:
        """Run a shell command and return the output, error, and optionally a screenshot."""
        _, stdout, stderr = await run(command)
        base64_image = None

        if take_screenshot:
            await asyncio.sleep(self._screenshot_delay)
            base64_image = (await self.screenshot()).base64_image

        return ToolResult(output=stdout, error=stderr, base64_image=base64_image)

    def validate_coordinate(
        self, coordinate: tuple[int, int] | None = None
    ) -> tuple[int, int]:
        """Validate that coordinates are within bounds."""
        if coordinate is None:
            raise ToolError("Coordinate cannot be None")
        if not isinstance(coordinate, (list, tuple)) or len(coordinate) != 2:
            raise ToolError(f"{coordinate} must be a tuple of length 2")
        if not all(isinstance(i, int) and i >= 0 for i in coordinate):
            raise ToolError(f"{coordinate} must be a tuple of non-negative ints")
        x, y = coordinate
        if x > self.width or y > self.height:
            raise ToolError(f"Coordinates {x}, {y} are out of bounds")
        return x, y


class BrowserTool20250910(BaseBrowserTool, BaseAnthropicTool):
    """Browser tool implementation for the browser_20250910 API."""

    api_type: Literal["browser_20250910"] = "browser_20250910"

    def to_params(self) -> BetaToolUnionParam:
        return cast(
            BetaToolUnionParam,
            {"name": self.name, "type": self.api_type, **self.options},
        )

    async def __call__(
        self,
        *,
        action: BrowserAction,
        text: str | None = None,
        coordinate: tuple[int, int] | None = None,
        start_coordinate: tuple[int, int] | None = None,
        end_coordinate: tuple[int, int] | None = None,
        direction: ScrollDirection | None = None,
        scroll_direction: ScrollDirection | None = None,
        amount: int | None = None,
        scroll_amount: int | None = None,
        target_y: int | None = None,
        key: str | None = None,
        selector: str | None = None,
        field_name: str | None = None,
        field_value: str | None = None,
        javascript: str | None = None,
        zoom_level: int | None = None,
        wait_time: float | None = None,
        **kwargs,
    ) -> ToolResult:
        """Execute browser actions."""

        direction = direction or scroll_direction
        amount = amount or scroll_amount

        if action == "navigate":
            if text is None:
                raise ToolError("URL is required for navigate action")

            # Ensure Firefox is running before trying to navigate
            if not await self.ensure_browser_running():
                raise ToolError("Failed to start Firefox browser")

            await self.shell(f"{self.xdotool} key ctrl+l", take_screenshot=False)
            await asyncio.sleep(0.5)
            await self.shell(
                f"{self.xdotool} type --delay 12 -- {shlex.quote(text)}",
                take_screenshot=False,
            )
            await self.shell(f"{self.xdotool} key Return")
            await asyncio.sleep(2)
            return await self.screenshot()

        elif action == "screenshot":
            return await self.screenshot()

        elif action in [
            "left_click",
            "right_click",
            "middle_click",
            "double_click",
            "triple_click",
        ]:
            if coordinate is None:
                raise ToolError(f"Coordinate is required for {action}")

            x, y = self.validate_coordinate(coordinate)

            click_commands = {
                "left_click": "click 1",
                "right_click": "click 3",
                "middle_click": "click 2",
                "double_click": "click --repeat 2 --delay 10 1",
                "triple_click": "click --repeat 3 --delay 10 1",
            }

            click_cmd = click_commands[action]
            command = f"{self.xdotool} mousemove --sync {x} {y} {click_cmd}"
            return await self.shell(command)

        elif action == "left_click_drag":
            if start_coordinate is None or coordinate is None:
                raise ToolError(
                    "start_coordinate and coordinate are required for left_click_drag"
                )

            x1, y1 = self.validate_coordinate(start_coordinate)
            x2, y2 = self.validate_coordinate(coordinate)

            command = f"{self.xdotool} mousemove --sync {x1} {y1} mousedown 1 mousemove --sync {x2} {y2} mouseup 1"
            return await self.shell(command)

        elif action == "left_mouse_down":
            if coordinate:
                x, y = self.validate_coordinate(coordinate)
                command = f"{self.xdotool} mousemove --sync {x} {y} mousedown 1"
            else:
                command = f"{self.xdotool} mousedown 1"
            return await self.shell(command)

        elif action == "left_mouse_up":
            if coordinate:
                x, y = self.validate_coordinate(coordinate)
                command = f"{self.xdotool} mousemove --sync {x} {y} mouseup 1"
            else:
                command = f"{self.xdotool} mouseup 1"
            return await self.shell(command)

        elif action == "scroll":
            if direction is None:
                raise ToolError("Direction is required for scroll action")
            if direction not in ["up", "down", "left", "right"]:
                raise ToolError(f"Invalid scroll direction: {direction}")

            scroll_amount = amount or 3
            scroll_button = {"up": 4, "down": 5, "left": 6, "right": 7}[direction]

            command_parts = [self.xdotool]
            if coordinate:
                x, y = self.validate_coordinate(coordinate)
                command_parts.append(f"mousemove --sync {x} {y}")
            command_parts.append(f"click --repeat {scroll_amount} {scroll_button}")

            return await self.shell(" ".join(command_parts))

        elif action == "scroll_to":
            if target_y is None:
                raise ToolError("target_y is required for scroll_to action")
            num_scrolls = max(1, target_y // 100)
            command = f"{self.xdotool} key --repeat {num_scrolls} Page_Down"
            return await self.shell(command)

        elif action == "type":
            if text is None:
                raise ToolError("Text is required for type action")
            command = f"{self.xdotool} type --delay 12 -- {shlex.quote(text)}"
            return await self.shell(command)

        elif action == "key":
            if key is None and text is None:
                raise ToolError("Key or text is required for key action")
            key_to_press = key or text
            command = f"{self.xdotool} key -- {key_to_press}"
            return await self.shell(command)

        elif action == "hold_key":
            if key is None and text is None:
                raise ToolError("Key or text is required for hold_key action")
            key_to_hold = key or text
            duration = wait_time or 1.0
            command = f"{self.xdotool} keydown {key_to_hold} sleep {duration} keyup {key_to_hold}"
            return await self.shell(command)

        elif action == "read_page":
            return await self.screenshot()

        elif action == "find":
            if text is None:
                raise ToolError("Text is required for find action")
            await self.shell(f"{self.xdotool} key ctrl+f", take_screenshot=False)
            await asyncio.sleep(0.5)
            await self.shell(
                f"{self.xdotool} type --delay 12 -- {shlex.quote(text)}",
                take_screenshot=False,
            )
            return await self.shell(f"{self.xdotool} key Return")

        elif action == "get_page_text":
            result = await self.screenshot()
            return result.replace(
                output="Page text extraction requires DOM access (not implemented)"
            )

        elif action == "wait":
            wait_seconds = wait_time or 2.0
            if wait_seconds > 10:
                raise ToolError("Wait time cannot exceed 10 seconds")
            await asyncio.sleep(wait_seconds)
            return await self.screenshot()

        elif action == "form_input":
            if field_name is None or field_value is None:
                raise ToolError(
                    "field_name and field_value are required for form_input"
                )
            if coordinate:
                x, y = self.validate_coordinate(coordinate)
                await self.shell(
                    f"{self.xdotool} mousemove --sync {x} {y} click 1",
                    take_screenshot=False,
                )
            await self.shell(
                f"{self.xdotool} type --delay 12 -- {shlex.quote(field_value)}",
            )
            return await self.screenshot()

        elif action == "javascript_exec":
            if javascript is None:
                raise ToolError("JavaScript code is required for javascript_exec")
            return ToolResult(
                output="JavaScript execution requires browser automation framework (not implemented)",
                base64_image=(await self.screenshot()).base64_image,
            )

        elif action == "zoom":
            if zoom_level is None:
                zoom_level = 100
            if zoom_level > 100:
                num_zooms = (zoom_level - 100) // 10
                command = f"{self.xdotool} key --repeat {num_zooms} ctrl+plus"
            elif zoom_level < 100:
                num_zooms = (100 - zoom_level) // 10
                command = f"{self.xdotool} key --repeat {num_zooms} ctrl+minus"
            else:
                command = f"{self.xdotool} key ctrl+0"
            return await self.shell(command)

        elif action == "close_browser":
            return await self.close_browser()

        else:
            raise ToolError(f"Unknown browser action: {action}")
