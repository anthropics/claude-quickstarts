from typing import Any, ClassVar

import pytest

from computer_use.tools.base import Tool
from computer_use.tools.result import ToolResult


def test_schema_signature_mismatch_raises():
    with pytest.raises(TypeError, match="does not accept"):

        class Bad(Tool):
            name = "bad"
            description = "x"
            input_schema: ClassVar[dict[str, Any]] = {
                "type": "object",
                "properties": {"a": {}, "b": {}},
            }

            def execute(self, *, a: str, **_: Any) -> ToolResult:  # missing b
                return ToolResult()


def test_required_with_default_raises():
    with pytest.raises(TypeError, match="required"):

        class Bad(Tool):
            name = "bad"
            description = "x"
            input_schema: ClassVar[dict[str, Any]] = {
                "type": "object",
                "properties": {"a": {}},
                "required": ["a"],
            }

            def execute(self, *, a: str = "x", **_: Any) -> ToolResult:
                return ToolResult()


def test_valid_tool_ok():
    class Good(Tool):
        name = "good"
        description = "x"
        input_schema: ClassVar[dict[str, Any]] = {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
        }

        def execute(self, *, a: str, **_: Any) -> ToolResult:
            return ToolResult(output=a)

    assert Good.to_param()["name"] == "good"


def test_delete_key_maps_to_backspace_on_mac():
    from computer_use.tools.computer import _translate_key

    assert _translate_key("delete") == "backspace"
    assert _translate_key("Delete") == "backspace"
    assert _translate_key("del") == "backspace"
    assert _translate_key("forward_delete") == "delete"
    assert _translate_key("backspace") == "backspace"


def test_unmapped_keys():
    from computer_use.tools.computer import _translate_key, _unmapped_keys

    assert _unmapped_keys(["command", "a"]) == []
    assert _unmapped_keys(["insert"]) == ["insert"]
    assert _unmapped_keys(["printscreen", "ctrl"]) == ["printscreen"]
    assert _unmapped_keys([_translate_key("win")]) == []


def test_browser_key_normalization():
    from computer_use.tools.browser import _to_playwright_chord

    assert _to_playwright_chord("ctrl+a") == "Control+a"
    assert _to_playwright_chord("cmd+shift+t") == "Meta+Shift+t"
    assert _to_playwright_chord("delete") == "Backspace"
    assert _to_playwright_chord("forward_delete") == "Delete"
    assert _to_playwright_chord("Enter") == "Enter"
    assert _to_playwright_chord("ctrl+ArrowLeft") == "Control+ArrowLeft"
    assert _to_playwright_chord("F5") == "F5"


def test_computer_tool_hosted_param():
    from computer_use.tools.computer import ComputerTool
    from constants import HOSTED_COMPUTER_TOOL_TYPE

    t = ComputerTool()
    p = t.to_hosted_param()
    assert p["type"] == HOSTED_COMPUTER_TOOL_TYPE
    assert p["name"] == "computer"
    assert isinstance(p["display_width_px"], int) and p["display_width_px"] > 0
    assert isinstance(p["display_height_px"], int) and p["display_height_px"] > 0


def test_tool_collection_hosted_computer_swap():
    from computer_use.tools.base import ToolCollection
    from computer_use.tools.computer import ComputerTool

    tc = ToolCollection(ComputerTool())
    explicit = tc.to_params(hosted_computer=False)[0]
    hosted = tc.to_params(hosted_computer=True)[0]
    assert "input_schema" in explicit
    assert "input_schema" not in hosted
    assert hosted["type"].startswith("computer_")
