"""Open or focus a macOS application by name via ``open -a``."""

import subprocess
from typing import Any, ClassVar

from .base import Tool
from .result import ToolResult


class OpenApplicationTool(Tool):
    name: ClassVar[str] = "open_application"
    description: ClassVar[str] = (
        "Launch or focus a macOS application by its display name (as shown in "
        "/Applications), e.g. 'Safari', 'Terminal', 'TextEdit'."
    )
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {"app_name": {"type": "string"}},
        "required": ["app_name"],
    }

    def execute(self, *, app_name: str, **_: Any) -> ToolResult:
        proc = subprocess.run(["open", "-a", app_name], capture_output=True, text=True)
        if proc.returncode != 0:
            return ToolResult(error=proc.stderr.strip() or f"failed to open {app_name!r}")

        return ToolResult(output=f"opened {app_name}")
