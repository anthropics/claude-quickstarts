"""
Text editor tool: view / create / str_replace / insert, confined to a per-run
scratch directory.

`view` understands more than text: image files are returned as image content
blocks (so the model sees the pixels) and PDFs as document content blocks (the
API renders them itself). Everything else is treated as UTF-8 text with
numbered lines.

The schema mirrors Anthropic's hosted `text_editor_20250728` tool but is
declared explicitly here so this demo never relies on a server-hosted type.
"""

import base64
from pathlib import Path
from typing import Any, ClassVar

from PIL import Image

from ..image import resize_and_encode
from .base import Tool
from .result import ToolResult

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


class EditorTool(Tool):
    name: ClassVar[str] = "editor"
    validates_own_input: ClassVar[bool] = True
    description: ClassVar[str] = (
        "View, create, and edit files inside the agent's scratch directory. "
        "Paths are relative to that directory; absolute paths and `..` "
        "segments that escape it are rejected. The directory persists for the "
        "duration of the run, so you can use it as working memory."
    )
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "enum": ["view", "create", "str_replace", "insert"],
                "description": (
                    "* view: show a file (text with line numbers, image as an "
                    "image block, PDF as a document block) or list a "
                    "directory.\n"
                    "* create: create or overwrite a file with `file_text`.\n"
                    "* str_replace: replace the single occurrence of `old_str` "
                    "with `new_str` in the file. Fails if `old_str` is "
                    "missing or not unique.\n"
                    "* insert: insert `new_str` after line `insert_line` "
                    "(0 inserts at the top)."
                ),
            },
            "path": {
                "type": "string",
                "description": (
                    "Path relative to the scratch directory, e.g. `notes.md` or `data/out.json`."
                ),
            },
            "view_range": {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 2,
                "maxItems": 2,
                "description": "[start, end] 1-indexed line range; -1 for end means EOF.",
            },
            "file_text": {"type": "string"},
            "old_str": {"type": "string"},
            "new_str": {"type": "string"},
            "insert_line": {"type": "integer", "minimum": 0},
        },
        "required": ["command", "path"],
    }

    def __init__(self, scratch_dir: Path) -> None:
        self._root = scratch_dir.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        """Resolve `path` inside the scratch root; raise if it would escape."""
        candidate = (self._root / path).resolve()
        if not candidate.is_relative_to(self._root):
            raise ValueError(f"path {path!r} escapes the scratch directory")
        return candidate

    def execute(self, **kwargs: Any) -> ToolResult:
        command = kwargs["command"]
        try:
            target = self._resolve(kwargs["path"])
        except ValueError as e:
            return ToolResult(error=str(e))

        if command == "view":
            return self._view(target, kwargs.get("view_range"))
        if command == "create":
            return self._create(target, kwargs.get("file_text", ""))
        if command == "str_replace":
            return self._str_replace(target, kwargs.get("old_str"), kwargs.get("new_str"))
        if command == "insert":
            return self._insert(target, kwargs.get("insert_line"), kwargs.get("new_str"))
        return ToolResult(error=f"unknown command {command!r}")

    def _view(self, target: Path, view_range: list[int] | None) -> ToolResult:
        if not target.exists():
            return ToolResult(error=f"{self._rel(target)} does not exist")

        if target.is_dir():
            entries = sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())
            body = "\n".join(entries) if entries else "(empty)"
            return ToolResult(output=f"{self._rel(target)}/\n{body}")

        suffix = target.suffix.lower()
        if suffix in _IMAGE_SUFFIXES:
            with Image.open(target) as img:
                b64, (w, h) = resize_and_encode(img.convert("RGB"), min_bytes=0)
            return ToolResult(output=f"{self._rel(target)} ({w}x{h})", base64_image=b64)

        if suffix == ".pdf":
            data = base64.standard_b64encode(target.read_bytes()).decode()
            return ToolResult(output=f"{self._rel(target)} (PDF)", base64_pdf=data)

        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        start, end = 1, len(lines)
        if view_range:
            start = max(1, view_range[0])
            end = len(lines) if view_range[1] == -1 else min(len(lines), view_range[1])
        numbered = "\n".join(
            f"{i:6d}\t{line}" for i, line in enumerate(lines[start - 1 : end], start)
        )
        header = f"{self._rel(target)} (lines {start}-{end} of {len(lines)})"
        return ToolResult(output=f"{header}\n{numbered}")

    def _create(self, target: Path, file_text: str) -> ToolResult:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file_text, encoding="utf-8")
        return ToolResult(output=f"wrote {len(file_text)} chars to {self._rel(target)}")

    def _str_replace(self, target: Path, old: str | None, new: str | None) -> ToolResult:
        if old is None or new is None:
            return ToolResult(error="str_replace requires `old_str` and `new_str`")
        if not target.is_file():
            return ToolResult(error=f"{self._rel(target)} is not a file")
        text = target.read_text(encoding="utf-8")
        count = text.count(old)
        if count == 0:
            return ToolResult(error=f"`old_str` not found in {self._rel(target)}")
        if count > 1:
            return ToolResult(
                error=f"`old_str` matched {count} times in {self._rel(target)}; must be unique"
            )
        target.write_text(text.replace(old, new, 1), encoding="utf-8")
        return ToolResult(output=f"replaced 1 occurrence in {self._rel(target)}")

    def _insert(self, target: Path, insert_line: int | None, new: str | None) -> ToolResult:
        if insert_line is None or new is None:
            return ToolResult(error="insert requires `insert_line` and `new_str`")
        if not target.is_file():
            return ToolResult(error=f"{self._rel(target)} is not a file")
        lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
        insert_line = max(0, min(insert_line, len(lines)))
        if new and not new.endswith("\n"):
            new += "\n"
        lines.insert(insert_line, new)
        target.write_text("".join(lines), encoding="utf-8")
        return ToolResult(output=f"inserted after line {insert_line} in {self._rel(target)}")

    def _rel(self, p: Path) -> str:
        return str(p.relative_to(self._root)) if p != self._root else "."
