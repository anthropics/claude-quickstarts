"""
Batch tools: run a sequence of computer/browser actions in one model turn.

A batch is a list of `{action, ...input}` dicts dispatched sequentially to the
underlying tool. Execution stops on the first error. Results (including any
screenshots produced along the way) are returned interleaved so the model
sees exactly what happened at each step.

Coordinates inside a batch refer to the screenshot taken *before* the batch
call (the underlying tool's scale state is not updated mid-batch unless the
batch itself contains a screenshot action).
"""

from typing import Any, ClassVar

from .base import Tool
from .browser import BrowserTool
from .computer import ComputerTool
from .result import IMAGE_OMITTED_ON_ERROR, ContentBlockParam, ToolResult, image_block


class _BatchResult(ToolResult):
    """ToolResult that renders a list of labelled sub-results."""

    def __init__(self, items: list[tuple[str, ToolResult]], error: str | None = None):
        super().__init__(error=error)
        self._items = items

    def to_api_content(self) -> list[ContentBlockParam]:
        blocks: list[ContentBlockParam] = []
        for label, r in self._items:
            text = r.error if r.is_error else (r.output or "(ok)")
            blocks.append({"type": "text", "text": f"[{label}] {text}"})
            if r.base64_image:
                if self.is_error:
                    blocks.append({"type": "text", "text": IMAGE_OMITTED_ON_ERROR})
                else:
                    blocks.append(image_block(r.base64_image))
        if self.error:
            blocks.append({"type": "text", "text": self.error})
        return blocks or [{"type": "text", "text": "(empty batch)"}]


def _batch_description(inner_name: str) -> str:
    return (
        f"Execute multiple `{inner_name}` actions sequentially in a single "
        f"turn. Stops on the first error. Each item is the same shape as a "
        f"single `{inner_name}` call. All coordinates refer to the screenshot "
        f"taken *before* this batch."
    )


def _batch_schema(inner_schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {"actions": {"type": "array", "minItems": 1, "items": inner_schema}},
        "required": ["actions"],
    }


class _BatchTool(Tool):
    """Shared batch execution; concrete subclasses bind the ClassVars."""

    validates_own_input: ClassVar[bool] = True

    def __init__(self, inner: Tool) -> None:
        self._inner = inner

    def execute(self, *, actions: list[dict[str, Any]], **_: Any) -> ToolResult:
        done: list[tuple[str, ToolResult]] = []
        for i, step in enumerate(actions):
            label = f"{i}:{step.get('action', '?')}"
            try:
                res = self._inner.execute(**step)
            except Exception as e:
                res = ToolResult(error=f"{type(e).__name__}: {e}")
            done.append((label, res))
            if res.is_error:
                remaining = len(actions) - i - 1
                return _BatchResult(
                    done,
                    error=(
                        f"batch stopped at actions[{i}] ({label}): {res.error} "
                        f"({i} completed, {remaining} skipped)"
                    ),
                )
        return _BatchResult(done)


class ComputerBatchTool(_BatchTool):
    name: ClassVar[str] = "computer_batch"
    description: ClassVar[str] = _batch_description("computer")
    input_schema: ClassVar[dict[str, Any]] = _batch_schema(ComputerTool.input_schema)

    def __init__(self, inner: ComputerTool) -> None:
        super().__init__(inner)


class BrowserBatchTool(_BatchTool):
    name: ClassVar[str] = "browser_batch"
    description: ClassVar[str] = _batch_description("browser")
    input_schema: ClassVar[dict[str, Any]] = _batch_schema(BrowserTool.input_schema)

    def __init__(self, inner: BrowserTool) -> None:
        super().__init__(inner)
