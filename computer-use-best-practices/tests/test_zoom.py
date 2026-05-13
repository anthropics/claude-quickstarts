from computer_use.tools.browser import BrowserTool
from computer_use.tools.computer import ComputerTool


def test_zoom_in_computer_schema() -> None:
    schema = ComputerTool.input_schema
    assert "zoom" in schema["properties"]["action"]["enum"]
    assert schema["properties"]["region"]["minItems"] == 4
    assert schema["properties"]["region"]["maxItems"] == 4


def test_zoom_in_browser_schema() -> None:
    schema = BrowserTool.input_schema
    assert "zoom" in schema["properties"]["action"]["enum"]
    assert "region" in schema["properties"]


def test_computer_zoom_validation() -> None:
    t = ComputerTool()
    assert "requires `region`" in (t._zoom(None).error or "")
    assert "requires `region`" in (t._zoom([1, 2, 3]).error or "")
    assert "x2 > x1" in (t._zoom([100, 100, 50, 200]).error or "")
    assert "y2 > y1" in (t._zoom([0, 100, 200, 50]).error or "")
