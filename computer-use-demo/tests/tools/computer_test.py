import base64
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from computer_use_demo.tools import computer as computer_module
from computer_use_demo.tools.collection import ToolCollection
from computer_use_demo.tools.computer import (
    ComputerTool20241022,
    ComputerTool20250124,
    ComputerTool20251124,
    ComputerToolset20260801,
    ScalingSource,
    ToolError,
    ToolResult,
)


@pytest.fixture(params=[ComputerTool20241022, ComputerTool20250124])
def computer_tool(request):
    return request.param()


async def call_computer_tool(computer_tool, **kwargs):
    return await computer_tool(**kwargs)


@pytest.mark.asyncio
async def test_computer_tool_mouse_move(computer_tool):
    with patch.object(computer_tool, "shell", new_callable=AsyncMock) as mock_shell:
        mock_shell.return_value = ToolResult(output="Mouse moved")
        result = await computer_tool(action="mouse_move", coordinate=[100, 200])
        mock_shell.assert_called_once_with(
            f"{computer_tool.xdotool} mousemove --sync 100 200"
        )
        assert result.output == "Mouse moved"


@pytest.mark.asyncio
async def test_computer_tool_20250124_left_click_drag_accepts_text_modifier():
    computer_tool = ComputerTool20250124()
    with patch.object(computer_tool, "shell", new_callable=AsyncMock) as mock_shell:
        mock_shell.return_value = ToolResult(output="Mouse dragged")
        result = await call_computer_tool(
            computer_tool,
            action="left_click_drag",
            start_coordinate=[0, 0],
            coordinate=[100, 100],
            text="ctrl",
        )
        mock_shell.assert_called_once_with(
            f"{computer_tool.xdotool} mousemove --sync 0 0 keydown ctrl mousedown 1 mousemove --sync 100 100 mouseup 1 keyup ctrl"
        )
        assert result.output == "Mouse dragged"


@pytest.mark.asyncio
async def test_computer_tool_20250124_left_click_drag_accepts_key_modifier():
    computer_tool = ComputerTool20250124()
    with patch.object(computer_tool, "shell", new_callable=AsyncMock) as mock_shell:
        mock_shell.return_value = ToolResult(output="Mouse dragged")
        result = await call_computer_tool(
            computer_tool,
            action="left_click_drag",
            start_coordinate=[0, 0],
            coordinate=[100, 100],
            key="ctrl",
        )
        mock_shell.assert_called_once_with(
            f"{computer_tool.xdotool} mousemove --sync 0 0 keydown ctrl mousedown 1 mousemove --sync 100 100 mouseup 1 keyup ctrl"
        )
        assert result.output == "Mouse dragged"


@pytest.mark.asyncio
async def test_computer_tool_20250124_left_click_drag_without_modifier():
    computer_tool = ComputerTool20250124()
    with patch.object(computer_tool, "shell", new_callable=AsyncMock) as mock_shell:
        mock_shell.return_value = ToolResult(output="Mouse dragged")
        result = await call_computer_tool(
            computer_tool,
            action="left_click_drag",
            start_coordinate=[0, 0],
            coordinate=[100, 100],
        )
        mock_shell.assert_called_once_with(
            f"{computer_tool.xdotool} mousemove --sync 0 0 mousedown 1 mousemove --sync 100 100 mouseup 1"
        )
        assert result.output == "Mouse dragged"


@pytest.mark.asyncio
async def test_computer_tool_20250124_left_click_drag_empty_text_uses_no_modifier():
    computer_tool = ComputerTool20250124()
    with patch.object(computer_tool, "shell", new_callable=AsyncMock) as mock_shell:
        mock_shell.return_value = ToolResult(output="Mouse dragged")
        result = await call_computer_tool(
            computer_tool,
            action="left_click_drag",
            start_coordinate=[0, 0],
            coordinate=[100, 100],
            text="",
        )
        mock_shell.assert_called_once_with(
            f"{computer_tool.xdotool} mousemove --sync 0 0 mousedown 1 mousemove --sync 100 100 mouseup 1"
        )
        assert result.output == "Mouse dragged"


@pytest.mark.asyncio
async def test_computer_tool_20250124_left_click_drag_requires_start_coordinate():
    computer_tool = ComputerTool20250124()
    with pytest.raises(
        ToolError, match="start_coordinate is required for left_click_drag"
    ):
        await call_computer_tool(
            computer_tool, action="left_click_drag", coordinate=[100, 100]
        )


@pytest.mark.asyncio
async def test_computer_tool_20241022_left_click_drag_rejects_text_modifier():
    computer_tool = ComputerTool20241022()
    with pytest.raises(ToolError, match="text is not accepted for left_click_drag"):
        await call_computer_tool(
            computer_tool,
            action="left_click_drag",
            start_coordinate=[0, 0],
            coordinate=[100, 100],
            text="ctrl",
        )


@pytest.mark.asyncio
async def test_computer_tool_type(computer_tool):
    with (
        patch.object(computer_tool, "shell", new_callable=AsyncMock) as mock_shell,
        patch.object(
            computer_tool, "screenshot", new_callable=AsyncMock
        ) as mock_screenshot,
    ):
        mock_shell.return_value = ToolResult(output="Text typed")
        mock_screenshot.return_value = ToolResult(base64_image="base64_screenshot")
        result = await computer_tool(action="type", text="Hello, World!")
        assert mock_shell.call_count == 1
        assert "type --delay 12 -- 'Hello, World!'" in mock_shell.call_args[0][0]
        assert result.output == "Text typed"
        assert result.base64_image == "base64_screenshot"


@pytest.mark.asyncio
async def test_computer_tool_screenshot(computer_tool):
    with patch.object(
        computer_tool, "screenshot", new_callable=AsyncMock
    ) as mock_screenshot:
        mock_screenshot.return_value = ToolResult(base64_image="base64_screenshot")
        result = await computer_tool(action="screenshot")
        mock_screenshot.assert_called_once()
        assert result.base64_image == "base64_screenshot"


@pytest.mark.asyncio
async def test_computer_tool_scaling(computer_tool):
    computer_tool._scaling_enabled = True
    computer_tool.width = 1920
    computer_tool.height = 1080

    # Test scaling from API to computer
    x, y = computer_tool.scale_coordinates(ScalingSource.API, 1366, 768)
    assert x == 1920
    assert y == 1080

    # Test scaling from computer to API
    x, y = computer_tool.scale_coordinates(ScalingSource.COMPUTER, 1920, 1080)
    assert x == 1366
    assert y == 768

    # Test no scaling when disabled
    computer_tool._scaling_enabled = False
    x, y = computer_tool.scale_coordinates(ScalingSource.API, 1366, 768)
    assert x == 1366
    assert y == 768


@pytest.mark.asyncio
async def test_computer_tool_scaling_with_different_aspect_ratio(computer_tool):
    computer_tool._scaling_enabled = True
    computer_tool.width = 1920
    computer_tool.height = 1200  # 16:10 aspect ratio

    # Test scaling from API to computer
    x, y = computer_tool.scale_coordinates(ScalingSource.API, 1280, 800)
    assert x == 1920
    assert y == 1200

    # Test scaling from computer to API
    x, y = computer_tool.scale_coordinates(ScalingSource.COMPUTER, 1920, 1200)
    assert x == 1280
    assert y == 800


@pytest.mark.asyncio
async def test_computer_tool_no_scaling_for_unsupported_resolution(computer_tool):
    computer_tool._scaling_enabled = True
    computer_tool.width = 4096
    computer_tool.height = 2160

    # Test no scaling for unsupported resolution
    x, y = computer_tool.scale_coordinates(ScalingSource.API, 4096, 2160)
    assert x == 4096
    assert y == 2160

    x, y = computer_tool.scale_coordinates(ScalingSource.COMPUTER, 4096, 2160)
    assert x == 4096
    assert y == 2160


@pytest.mark.asyncio
async def test_computer_tool_scaling_out_of_bounds(computer_tool):
    computer_tool._scaling_enabled = True
    computer_tool.width = 1920
    computer_tool.height = 1080

    # Test scaling from API with out of bounds coordinates
    with pytest.raises(ToolError, match="Coordinates .*, .* are out of bounds"):
        x, y = computer_tool.scale_coordinates(ScalingSource.API, 2000, 1500)


@pytest.mark.asyncio
async def test_computer_tool_invalid_action(computer_tool):
    with pytest.raises(ToolError, match="Invalid action: invalid_action"):
        await computer_tool(action="invalid_action")


@pytest.mark.asyncio
async def test_computer_tool_missing_coordinate(computer_tool):
    with pytest.raises(ToolError, match="coordinate is required for mouse_move"):
        await computer_tool(action="mouse_move")


@pytest.mark.asyncio
async def test_computer_tool_missing_text(computer_tool):
    with pytest.raises(ToolError, match="text is required for type"):
        await computer_tool(action="type")


@pytest.fixture
def computer_toolset():
    return ComputerToolset20260801()


def test_computer_toolset_to_params_is_a_nameless_entry(computer_toolset):
    assert computer_toolset.to_params() == {"type": "computer_toolset_20260801"}


@pytest.mark.asyncio
async def test_computer_toolset_key_repeat(computer_toolset):
    with patch.object(computer_toolset, "shell", new_callable=AsyncMock) as mock_shell:
        mock_shell.return_value = ToolResult(output="Pressed")
        await computer_toolset(action="key", text="Down", repeat=3)
        mock_shell.assert_called_once_with(
            f"{computer_toolset.xdotool} key -- Down Down Down"
        )


@pytest.mark.asyncio
async def test_computer_toolset_key_repeat_quotes_each_key(computer_toolset):
    with patch.object(computer_toolset, "shell", new_callable=AsyncMock) as mock_shell:
        mock_shell.return_value = ToolResult(output="Pressed")
        await computer_toolset(action="key", text="Down; rm -rf /", repeat=2)
        mock_shell.assert_called_once_with(
            f"{computer_toolset.xdotool} key -- 'Down; rm -rf /' 'Down; rm -rf /'"
        )


@pytest.mark.asyncio
async def test_computer_toolset_key_without_repeat_takes_the_quoted_path(
    computer_toolset,
):
    with patch.object(computer_toolset, "shell", new_callable=AsyncMock) as mock_shell:
        mock_shell.return_value = ToolResult(output="Pressed")
        await computer_toolset(action="key", text="ctrl+shift+(")
        mock_shell.assert_called_once_with(
            f"{computer_toolset.xdotool} key -- 'ctrl+shift+('"
        )


@pytest.mark.asyncio
async def test_computer_toolset_key_rejects_coordinate(computer_toolset):
    with pytest.raises(ToolError, match="coordinate is not accepted"):
        await computer_toolset(action="key", text="a", coordinate=[1, 2])


@pytest.mark.asyncio
async def test_computer_toolset_key_repeat_out_of_bounds(computer_toolset):
    with pytest.raises(ToolError, match="must be an integer between 1 and 100"):
        await computer_toolset(action="key", text="Down", repeat=101)


@pytest.mark.asyncio
async def test_computer_toolset_click_accepts_text_modifier(computer_toolset):
    with patch.object(computer_toolset, "shell", new_callable=AsyncMock) as mock_shell:
        mock_shell.return_value = ToolResult(output="Clicked")
        await computer_toolset(action="left_click", coordinate=[100, 200], text="ctrl")
        command = mock_shell.call_args[0][0]
        assert "keydown ctrl" in command
        assert "click 1" in command
        assert "keyup ctrl" in command


@pytest.mark.asyncio
async def test_computer_toolset_drag_accepts_text_modifier(computer_toolset):
    with patch.object(computer_toolset, "shell", new_callable=AsyncMock) as mock_shell:
        mock_shell.return_value = ToolResult(output="Dragged")
        await computer_toolset(
            action="left_click_drag",
            start_coordinate=[10, 20],
            coordinate=[30, 40],
            text="shift",
        )
        command = mock_shell.call_args[0][0]
        assert command.index("keydown shift") < command.index("mousedown 1")
        assert command.index("mouseup 1") < command.index("keyup shift")


@pytest.mark.asyncio
async def test_computer_toolset_invalid_member(computer_toolset):
    with pytest.raises(ToolError, match="Invalid member tool: navigate"):
        await computer_toolset(action="navigate")


@pytest.mark.asyncio
async def test_tool_collection_routes_member_calls(computer_toolset):
    collection = ToolCollection(computer_toolset)
    with patch.object(
        computer_toolset, "screenshot", new_callable=AsyncMock
    ) as mock_screenshot:
        mock_screenshot.return_value = ToolResult(base64_image="base64_screenshot")
        result = await collection.run(
            name="screenshot", tool_input={}, toolset_name="computer"
        )
        assert result.base64_image == "base64_screenshot"

    unknown = await collection.run(
        name="screenshot", tool_input={}, toolset_name="browser"
    )
    assert unknown.error == "Toolset browser is invalid"


@pytest.fixture
def zoom_capture(tmp_path):
    """Stand in for the display capture and ImageMagick: records the convert
    command and materializes the files each step expects to find."""
    commands: list[str] = []

    async def fake_capture(self, path):
        path.write_bytes(b"raw")
        return ToolResult()

    async def fake_run(command):
        commands.append(command)
        # The output path is the last token of the convert command.
        Path(command.split()[-1]).write_bytes(b"zoomed")  # noqa: ASYNC240
        return 0, "", ""

    with (
        patch.object(computer_module.BaseComputerTool, "_capture", fake_capture),
        patch.object(computer_module, "run", fake_run),
        patch.object(computer_module, "OUTPUT_DIR", str(tmp_path)),
    ):
        yield commands


@pytest.mark.asyncio
async def test_zoom_crops_the_physical_capture_and_fits_the_screenshot_frame(
    zoom_capture,
):
    tool = ComputerTool20251124()
    # 2048x1536 scales down to XGA (1024x768), so screenshot pixels are half
    # of physical pixels: the crop must be taken in physical pixels and the
    # result fitted back into the 1024x768 frame the model sees.
    tool.width, tool.height = 2048, 1536

    result = await tool(action="zoom", region=(100, 100, 300, 200))

    assert result.base64_image == base64.b64encode(b"zoomed").decode()
    (command,) = zoom_capture
    assert "-crop 400x200+200+200 +repage" in command
    assert "-resize 1024x768 " in command


@pytest.mark.asyncio
async def test_zoom_without_scaling_uses_screenshot_pixels_directly(zoom_capture):
    tool = ComputerTool20251124()  # 1024x768 from conftest: no scaling target

    await tool(action="zoom", region=(10, 20, 110, 70))

    (command,) = zoom_capture
    assert "-crop 100x50+10+20 +repage" in command
    assert "-resize 1024x768 " in command


@pytest.mark.asyncio
async def test_zoom_is_a_toolset_member(zoom_capture, computer_toolset):
    result = await ToolCollection(computer_toolset).run(
        name="zoom", tool_input={"region": [0, 0, 50, 50]}, toolset_name="computer"
    )
    assert result.base64_image
    assert "-crop 50x50+0+0" in zoom_capture[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "region,message",
    [
        (None, "must be a tuple of 4 coordinates"),
        ([0, 0, 10], "must be a tuple of 4 coordinates"),
        ([0, 0, -1, 10], "non-negative integers"),
        ([50, 0, 50, 10], "x0 < x1 and y0 < y1"),
        ([0, 60, 10, 20], "x0 < x1 and y0 < y1"),
    ],
)
async def test_zoom_rejects_malformed_regions(zoom_capture, region, message):
    with pytest.raises(ToolError, match=message):
        await ComputerTool20251124()(action="zoom", region=region)
    assert zoom_capture == []
