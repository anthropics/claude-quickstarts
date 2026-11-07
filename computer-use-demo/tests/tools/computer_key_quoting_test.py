import shlex
from pathlib import Path
from typing import Any, Literal
from unittest.mock import AsyncMock, patch

import pytest

from computer_use_demo.tools.computer import (
    BaseComputerTool,
    ComputerTool20241022,
    ComputerTool20250124,
    ComputerTool20251124,
    ComputerToolset20260801,
    ToolResult,
)


@pytest.fixture
def xdotool_command(tmp_path: Path) -> str:
    executable = tmp_path / "xdotool"
    executable.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
    executable.chmod(0o755)
    return shlex.quote(str(executable))


@pytest.mark.parametrize(
    "tool_class", [ComputerTool20241022, ComputerTool20250124, ComputerTool20251124]
)
@pytest.mark.parametrize("text", [";", "'", "ctrl+$(printf substituted)"])
async def test_key_preserves_literal_shell_characters(
    tool_class: type[BaseComputerTool], text: str, xdotool_command: str
) -> None:
    tool = tool_class()
    tool.xdotool = xdotool_command
    tool._screenshot_delay = 0
    with patch.object(tool, "screenshot", AsyncMock(return_value=ToolResult())):
        result = await tool(action="key", text=text)

    assert result.error == ""
    assert result.output is not None
    assert result.output.splitlines() == ["key", "--", text]


@pytest.mark.parametrize(
    "tool_class", [ComputerTool20250124, ComputerTool20251124, ComputerToolset20260801]
)
@pytest.mark.parametrize("action", ["left_click", "scroll"])
async def test_pointer_modifiers_preserve_literal_shell_characters(
    tool_class: type[ComputerTool20250124],
    action: Literal["left_click", "scroll"],
    xdotool_command: str,
) -> None:
    tool = tool_class()
    tool.xdotool = xdotool_command
    tool._screenshot_delay = 0
    text = "ctrl+$(printf substituted)"
    kwargs: dict[str, Any]
    if action == "scroll":
        kwargs = {"text": text, "scroll_direction": "up", "scroll_amount": 1}
        click_arguments = ["click", "--repeat", "1", "4"]
    else:
        kwargs = {"text" if tool_class is ComputerToolset20260801 else "key": text}
        click_arguments = ["click", "1"]
    with patch.object(tool, "screenshot", AsyncMock(return_value=ToolResult())):
        result = await tool(action=action, **kwargs)

    assert result.error == ""
    assert result.output is not None
    assert result.output.splitlines() == [
        "keydown",
        text,
        *click_arguments,
        "keyup",
        text,
    ]
