#!/usr/bin/env python3
"""Regression tests for file tool workspace-root confinement."""

import asyncio
import os
import sys
import tempfile
import types
from pathlib import Path

# Load agents.tools without importing agents/__init__.py (needs anthropic).
_AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_AGENTS_DIR)
sys.path.insert(0, _REPO_ROOT)

_agents = types.ModuleType("agents")
_agents.__path__ = [_AGENTS_DIR]
sys.modules["agents"] = _agents

_tools = types.ModuleType("agents.tools")
_tools.__path__ = [os.path.join(_AGENTS_DIR, "tools")]
sys.modules["agents.tools"] = _tools

from agents.tools.file_tools import FileReadTool, FileWriteTool  # noqa: E402


async def _run() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        outside = root.parent / f"claude-quickstarts-escape-{os.getpid()}.txt"
        (root / "safe.txt").write_text("hello-inside", encoding="utf-8")
        (root / "subdir").mkdir()
        (root / "subdir" / "nested.txt").write_text("nested", encoding="utf-8")

        read = FileReadTool(root=root)
        write = FileWriteTool(root=root)

        # In-root read / write / edit still work
        assert "hello-inside" in await read.execute("read", "safe.txt")
        assert "Successfully wrote" in await write.execute(
            "write", "new.txt", content="created"
        )
        assert (root / "new.txt").read_text(encoding="utf-8") == "created"
        assert "Successfully edited" in await write.execute(
            "edit", "new.txt", old_text="created", new_text="updated"
        )
        assert (root / "new.txt").read_text(encoding="utf-8") == "updated"

        listed = await read.execute("list", ".", pattern="*.txt")
        assert "safe.txt" in listed
        assert "new.txt" in listed

        # Parent-segment and absolute escapes are rejected
        for escape_path in (
            "../escape.txt",
            str(outside),
            "subdir/../../escape.txt",
        ):
            result = await write.execute(
                "write", escape_path, content="should-not-write"
            )
            assert "outside the workspace root" in result, result
            assert not outside.exists(), f"wrote outside via {escape_path}"

            result = await read.execute("read", escape_path)
            assert "outside the workspace root" in result, result

            result = await write.execute(
                "edit",
                escape_path,
                old_text="a",
                new_text="b",
            )
            assert "outside the workspace root" in result, result

        # Glob patterns must not escape via .. or absolute segments
        result = await read.execute("list", ".", pattern="../**")
        assert "relative glob" in result

        result = await read.execute("list", str(root.parent), pattern="*")
        assert "outside the workspace root" in result

        # Absolute path inside the root remains allowed
        inside_abs = str(root / "safe.txt")
        assert "hello-inside" in await read.execute("read", inside_abs)

    print("All file tool confinement tests passed")


if __name__ == "__main__":
    asyncio.run(_run())
