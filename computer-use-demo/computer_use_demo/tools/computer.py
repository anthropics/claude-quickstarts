import asyncio
import base64
import os
import shlex
import shutil
from enum import StrEnum
from pathlib import Path
from typing import Literal, TypedDict, cast, get_args
from uuid import uuid4

from anthropic.types.beta import BetaToolComputerUse20241022Param, BetaToolUnionParam

from .base import BaseAnthropicTool, ToolError, ToolResult
from .run import run

OUTPUT_DIR = "/tmp/outputs"

TYPING_DELAY_MS = 12
TYPING_GROUP_SIZE = 50

Action_20241022 = Literal[
    "key",
    "type",
    "mouse_move",
    "left_click",
    "left_click_drag",
    "right_click",
    "middle_click",
    "double_click",
    "screenshot",
    "cursor_position",
]

Action_20250124 = (
    Action_20241022
    | Literal[
        "left_mouse_down",
        "left_mouse_up",
        "scroll",
        "hold_key",
        "wait",
        "triple_click",
    ]
)

ScrollDirection = Literal["up", "down", "left", "right"]


class Resolution(TypedDict):
    width: int
    height: int


# sizes above XGA/WXGA are not recommended (see README.md)
# scale down to one of these targets if ComputerTool._scaling_enabled is set
MAX_SCALING_TARGETS: dict[str, Resolution] = {
    "XGA": Resolution(width=1024, height=768),  # 4:3
    "WXGA": Resolution(width=1280, height=800),  # 16:10
    "FWXGA": Resolution(width=1366, height=768),  # ~16:9
}

CLICK_BUTTONS = {
    "left_click": 1,
    "right_click": 3,
    "middle_click": 2,
    "double_click": "--repeat 2 --delay 10 1",
    "triple_click": "--repeat 3 --delay 10 1",
}


class ScalingSource(StrEnum):
    COMPUTER = "computer"
    API = "api"


class ComputerToolOptions(TypedDict):
    display_height_px: int
    display_width_px: int
    display_number: int | None


def chunks(s: str, chunk_size: int) -> list[str]:
    return [s[i : i + chunk_size] for i in range(0, len(s), chunk_size)]


class BaseComputerTool:
    """
    A tool that allows the agent to interact with the screen, keyboard, and mouse of the current computer.
    The tool parameters are defined by Anthropic and are not editable.
    """

    name: Literal["computer"] = "computer"
    width: int
    height: int
    display_num: int | None

    _screenshot_delay = 2.0
    _scaling_enabled = True

    @property
    def options(self) -> ComputerToolOptions:
        width, height = self.scale_coordinates(
            ScalingSource.COMPUTER, self.width, self.height
        )
        return {
            "display_width_px": width,
            "display_height_px": height,
            "display_number": self.display_num,
        }

    def __init__(self):
        super().__init__()

        self.width = int(os.getenv("WIDTH") or 0)
        self.height = int(os.getenv("HEIGHT") or 0)
        assert self.width and self.height, "WIDTH, HEIGHT must be set"
        if (display_num := os.getenv("DISPLAY_NUM")) is not None:
            self.display_num = int(display_num)
            self._display_prefix = f"DISPLAY=:{self.display_num} "
        else:
            self.display_num = None
            self._display_prefix = ""

        self.xdotool = f"{self._display_prefix}xdotool"

    async def __call__(
        self,
        *,
        action: Action_20241022,
        text: str | None = None,
        coordinate: tuple[int, int] | None = None,
        **kwargs,
    ):
        if action in ("mouse_move", "left_click_drag"):
            if coordinate is None:
                raise ToolError(f"coordinate is required for {action}")
            if text is not None:
                raise ToolError(f"text is not accepted for {action}")

            x, y = self.validate_and_get_coordinates(coordinate)

            if action == "mouse_move":
                command_parts = [self.xdotool, f"mousemove --sync {x} {y}"]
                return await self.shell(" ".join(command_parts))
            elif action == "left_click_drag":
                command_parts = [
                    self.xdotool,
                    f"mousedown 1 mousemove --sync {x} {y} mouseup 1",
                ]
                return await self.shell(" ".join(command_parts))

        if action in ("key", "type"):
            if text is None:
                raise ToolError(f"text is required for {action}")
            if coordinate is not None:
                raise ToolError(f"coordinate is not accepted for {action}")
            if not isinstance(text, str):
                raise ToolError(output=f"{text} must be a string")

            if action == "key":
                command_parts = [self.xdotool, f"key -- {text}"]
                return await self.shell(" ".join(command_parts))
            elif action == "type":
                results: list[ToolResult] = []
                for chunk in chunks(text, TYPING_GROUP_SIZE):
                    command_parts = [
                        self.xdotool,
                        f"type --delay {TYPING_DELAY_MS} -- {shlex.quote(chunk)}",
                    ]
                    results.append(
                        await self.shell(" ".join(command_parts), take_screenshot=False)
                    )
                screenshot_base64 = (await self.screenshot()).base64_image
                return ToolResult(
                    output="".join(result.output or "" for result in results),
                    error="".join(result.error or "" for result in results),
                    base64_image=screenshot_base64,
                )

        if action in (
            "left_click",
            "right_click",
            "double_click",
            "middle_click",
            "screenshot",
            "cursor_position",
        ):
            if text is not None:
                raise ToolError(f"text is not accepted for {action}")
            if coordinate is not None:
                raise ToolError(f"coordinate is not accepted for {action}")

            if action == "screenshot":
                return await self.screenshot()
            elif action == "cursor_position":
                command_parts = [self.xdotool, "getmouselocation --shell"]
                result = await self.shell(
                    " ".join(command_parts),
                    take_screenshot=False,
                )
                output = result.output or ""
                x, y = self.scale_coordinates(
                    ScalingSource.COMPUTER,
                    int(output.split("X=")[1].split("\n")[0]),
                    int(output.split("Y=")[1].split("\n")[0]),
                )
                return result.replace(output=f"X={x},Y={y}")
            else:
                command_parts = [self.xdotool, f"click {CLICK_BUTTONS[action]}"]
                return await self.shell(" ".join(command_parts))

        raise ToolError(f"Invalid action: {action}")

    def validate_and_get_coordinates(self, coordinate: tuple[int, int] | None = None):
        if not isinstance(coordinate, list) or len(coordinate) != 2:
            raise ToolError(f"{coordinate} must be a tuple of length 2")
        if not all(isinstance(i, int) and i >= 0 for i in coordinate):
            raise ToolError(f"{coordinate} must be a tuple of non-negative ints")

        return self.scale_coordinates(ScalingSource.API, coordinate[0], coordinate[1])

    async def screenshot(self):
        """Take a screenshot of the current screen and return the base64 encoded image."""
        output_dir = Path(OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"screenshot_{uuid4().hex}.png"

        # Try gnome-screenshot first
        if shutil.which("gnome-screenshot"):
            screenshot_cmd = f"{self._display_prefix}gnome-screenshot -f {path} -p"
        else:
            # Fall back to scrot if gnome-screenshot isn't available
            screenshot_cmd = f"{self._display_prefix}scrot -p {path}"

        result = await self.shell(screenshot_cmd, take_screenshot=False)
        if self._scaling_enabled:
            x, y = self.scale_coordinates(
                ScalingSource.COMPUTER, self.width, self.height
            )
            await self.shell(
                f"convert {path} -resize {x}x{y}! {path}", take_screenshot=False
            )

        if path.exists():
            return result.replace(
                base64_image=base64.b64encode(path.read_bytes()).decode()
            )
        raise ToolError(f"Failed to take screenshot: {result.error}")

    async def shell(self, command: str, take_screenshot=True) -> ToolResult:
        """Run a shell command and return the output, error, and optionally a screenshot."""
        _, stdout, stderr = await run(command)
        base64_image = None

        if take_screenshot:
            # delay to let things settle before taking a screenshot
            await asyncio.sleep(self._screenshot_delay)
            base64_image = (await self.screenshot()).base64_image

        return ToolResult(output=stdout, error=stderr, base64_image=base64_image)

    def scale_coordinates(self, source: ScalingSource, x: int, y: int):
        """Scale coordinates to a target maximum resolution."""
        if not self._scaling_enabled:
            return x, y
        ratio = self.width / self.height
        target_dimension = None
        for dimension in MAX_SCALING_TARGETS.values():
            # allow some error in the aspect ratio - not ratios are exactly 16:9
            if abs(dimension["width"] / dimension["height"] - ratio) < 0.02:
                if dimension["width"] < self.width:
                    target_dimension = dimension
                break
        if target_dimension is None:
            return x, y
        # should be less than 1
        x_scaling_factor = target_dimension["width"] / self.width
        y_scaling_factor = target_dimension["height"] / self.height
        if source == ScalingSource.API:
            if x > self.width or y > self.height:
                raise ToolError(f"Coordinates {x}, {y} are out of bounds")
            # scale up
            return round(x / x_scaling_factor), round(y / y_scaling_factor)
        # scale down
        return round(x * x_scaling_factor), round(y * y_scaling_factor)


class ComputerTool20241022(BaseComputerTool, BaseAnthropicTool):
    api_type: Literal["computer_20241022"] = "computer_20241022"

    def to_params(self) -> BetaToolComputerUse20241022Param:
        return {"name": self.name, "type": self.api_type, **self.options}


class ComputerTool20250124(BaseComputerTool, BaseAnthropicTool):
    api_type: Literal["computer_20250124"] = "computer_20250124"

    def to_params(self):
        return cast(
            BetaToolUnionParam,
            {"name": self.name, "type": self.api_type, **self.options},
        )

    async def __call__(
        self,
        *,
        action: Action_20250124,
        text: str | None = None,
        coordinate: tuple[int, int] | None = None,
        scroll_direction: ScrollDirection | None = None,
        scroll_amount: int | None = None,
        duration: int | float | None = None,
        key: str | None = None,
        **kwargs,
    ):
        if action in ("left_mouse_down", "left_mouse_up"):
            if coordinate is not None:
                raise ToolError(f"coordinate is not accepted for {action=}.")
            command_parts = [
                self.xdotool,
                f"{'mousedown' if action == 'left_mouse_down' else 'mouseup'} 1",
            ]
            return await self.shell(" ".join(command_parts))
        if action == "scroll":
            if scroll_direction is None or scroll_direction not in get_args(
                ScrollDirection
            ):
                raise ToolError(
                    f"{scroll_direction=} must be 'up', 'down', 'left', or 'right'"
                )
            if not isinstance(scroll_amount, int) or scroll_amount < 0:
                raise ToolError(f"{scroll_amount=} must be a non-negative int")
            mouse_move_part = ""
            if coordinate is not None:
                x, y = self.validate_and_get_coordinates(coordinate)
                mouse_move_part = f"mousemove --sync {x} {y}"
            scroll_button = {
                "up": 4,
                "down": 5,
                "left": 6,
                "right": 7,
            }[scroll_direction]

            command_parts = [self.xdotool, mouse_move_part]
            if text:
                command_parts.append(f"keydown {text}")
            command_parts.append(f"click --repeat {scroll_amount} {scroll_button}")
            if text:
                command_parts.append(f"keyup {text}")

            return await self.shell(" ".join(command_parts))

        if action in ("hold_key", "wait"):
            if duration is None or not isinstance(duration, (int, float)):
                raise ToolError(f"{duration=} must be a number")
            if duration < 0:
                raise ToolError(f"{duration=} must be non-negative")
            if duration > 100:
                raise ToolError(f"{duration=} is too long.")

            if action == "hold_key":
                if text is None:
                    raise ToolError(f"text is required for {action}")
                escaped_keys = shlex.quote(text)
                command_parts = [
                    self.xdotool,
                    f"keydown {escaped_keys}",
                    f"sleep {duration}",
                    f"keyup {escaped_keys}",
                ]
                return await self.shell(" ".join(command_parts))

            if action == "wait":
                await asyncio.sleep(duration)
                return await self.screenshot()

        if action in (
            "left_click",
            "right_click",
            "double_click",
            "triple_click",
            "middle_click",
        ):
            if text is not None:
                raise ToolError(f"text is not accepted for {action}")
            mouse_move_part = ""
            if coordinate is not None:
                x, y = self.validate_and_get_coordinates(coordinate)
                mouse_move_part = f"mousemove --sync {x} {y}"

            command_parts = [self.xdotool, mouse_move_part]
            if key:
                command_parts.append(f"keydown {key}")
            command_parts.append(f"click {CLICK_BUTTONS[action]}")
            if key:
                command_parts.append(f"keyup {key}")

            return await self.shell(" ".join(command_parts))

        return await super().__call__(
            action=action, text=text, coordinate=coordinate, key=key, **kwargs
        )
