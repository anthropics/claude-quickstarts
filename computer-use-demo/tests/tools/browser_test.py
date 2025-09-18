import pytest

from computer_use_demo.tools.browser import BrowserTool20250910, ToolError


@pytest.fixture
def browser_tool():
    return BrowserTool20250910()


@pytest.mark.asyncio
async def test_browser_tool_initialization(browser_tool):
    assert browser_tool.name == "browser"
    assert browser_tool.api_type == "browser_20250910"
    assert browser_tool.width > 0
    assert browser_tool.height > 0


def test_browser_tool_to_params(browser_tool):
    params = browser_tool.to_params()
    assert params["name"] == "browser"
    assert params["type"] == "browser_20250910"
    assert "display_width_px" in params
    assert "display_height_px" in params
    assert "display_number" in params


def test_browser_tool_validate_coordinate(browser_tool):
    x, y = browser_tool.validate_coordinate((100, 200))
    assert x == 100
    assert y == 200


def test_browser_tool_validate_coordinate_none(browser_tool):
    with pytest.raises(ToolError, match="Coordinate cannot be None"):
        browser_tool.validate_coordinate(None)


def test_browser_tool_validate_coordinate_invalid_format(browser_tool):
    with pytest.raises(ToolError, match="must be a tuple of length 2"):
        browser_tool.validate_coordinate((100,))


def test_browser_tool_validate_coordinate_negative(browser_tool):
    with pytest.raises(ToolError, match="must be a tuple of non-negative ints"):
        browser_tool.validate_coordinate((-1, 100))


def test_browser_tool_validate_coordinate_out_of_bounds(browser_tool):
    with pytest.raises(ToolError, match="are out of bounds"):
        browser_tool.validate_coordinate((10000, 10000))


@pytest.mark.asyncio
async def test_browser_tool_navigate_missing_url(browser_tool):
    with pytest.raises(ToolError, match="URL is required for navigate action"):
        await browser_tool(action="navigate")


@pytest.mark.asyncio
async def test_browser_tool_click_missing_coordinate(browser_tool):
    with pytest.raises(ToolError, match="Coordinate is required for left_click"):
        await browser_tool(action="left_click")


@pytest.mark.asyncio
async def test_browser_tool_type_missing_text(browser_tool):
    with pytest.raises(ToolError, match="Text is required for type action"):
        await browser_tool(action="type")


@pytest.mark.asyncio
async def test_browser_tool_scroll_missing_direction(browser_tool):
    with pytest.raises(ToolError, match="Direction is required for scroll action"):
        await browser_tool(action="scroll")


@pytest.mark.asyncio
async def test_browser_tool_scroll_invalid_direction(browser_tool):
    with pytest.raises(ToolError, match="Invalid scroll direction"):
        await browser_tool(action="scroll", direction="invalid")


@pytest.mark.asyncio
async def test_browser_tool_unknown_action(browser_tool):
    with pytest.raises(ToolError, match="Unknown browser action"):
        await browser_tool(action="unknown_action")
