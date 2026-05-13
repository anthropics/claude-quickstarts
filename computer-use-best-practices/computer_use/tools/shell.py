"""
Sandboxed bash and python execution.

Both tools wrap the user's script in `sandbox-exec` with the profile at
constants.SANDBOX_PROFILE. The default profile allows reading the filesystem
*except* secret paths (~/.ssh, ~/.aws, ~/.gnupg, .env, …), allows writing only
to a per-call scratch directory (passed via -D SCRATCH=…), and denies all
network. Edit the .sb file to loosen.
"""

import os
import select
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, ClassVar

from constants import SANDBOX_PROFILE, cfg

from .base import Tool
from .result import ToolResult

_TIMEOUT_S = 30


def _run_sandboxed(argv: list[str], scratch: Path) -> ToolResult:
    """Run argv under sandbox-exec, capping both wall-clock time and captured
    output. stdout and stderr are merged so the cap applies to the total."""
    cmd = [
        "sandbox-exec",
        "-f",
        str(SANDBOX_PROFILE),
        "-D",
        f"SCRATCH={scratch}",
        "-D",
        f"HOME={Path.home()}",
        *argv,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=scratch)
    assert proc.stdout is not None
    buf = bytearray()
    deadline = time.monotonic() + _TIMEOUT_S
    truncated = False
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            proc.kill()
            proc.wait()
            return ToolResult(error=f"timed out after {_TIMEOUT_S}s")
        ready, _, _ = select.select([proc.stdout], [], [], min(remaining, 0.5))
        if ready:
            chunk = os.read(proc.stdout.fileno(), 4096)
            if not chunk:
                break
            buf.extend(chunk)
            if len(buf) > cfg.max_shell_output_bytes:
                truncated = True
                proc.kill()
                break
        elif proc.poll() is not None:
            # Drain anything that landed between select() timing out and
            # poll() running; the writer is dead so this returns immediately.
            buf.extend(proc.stdout.read())
            break
    proc.wait()
    out = bytes(buf[: cfg.max_shell_output_bytes]).decode("utf-8", "replace")
    if truncated:
        out += f"\n[output truncated at {cfg.max_shell_output_bytes} bytes]"
    elif proc.returncode != 0:
        return ToolResult(error=out or f"exit {proc.returncode}")
    return ToolResult(output=out or "(no output)")


class _SandboxedTool(Tool):
    """Shared scratch-directory handling for bash and python.

    If a `scratch_dir` is provided at construction (the per-run directory under
    `runs/<ts>/scratch/`), it is reused on every call so state persists across
    tool invocations. Otherwise each call gets a fresh temp dir.
    """

    def __init__(self, scratch_dir: Path | None = None) -> None:
        self._scratch = scratch_dir.resolve() if scratch_dir else None

    def _run(self, source: str, interpreter: list[str], suffix: str) -> ToolResult:
        if self._scratch is not None:
            self._scratch.mkdir(parents=True, exist_ok=True)
            fd, path = tempfile.mkstemp(suffix=suffix, dir=self._scratch)
            os.close(fd)
            script = Path(path)
            try:
                script.write_text(source)
                return _run_sandboxed([*interpreter, str(script)], self._scratch)
            finally:
                script.unlink(missing_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp).resolve()
            script = scratch / f"script{suffix}"
            script.write_text(source)
            return _run_sandboxed([*interpreter, str(script)], scratch)


class BashTool(_SandboxedTool):
    name: ClassVar[str] = "bash"
    description: ClassVar[str] = (
        "Run a bash script inside a restrictive macOS sandbox. No network. "
        "CWD is the run's scratch directory; writes elsewhere are denied. "
        "30s timeout."
    )
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    }

    def execute(self, *, command: str, **_: Any) -> ToolResult:
        return self._run(command, ["/bin/bash"], ".sh")


class PythonTool(_SandboxedTool):
    name: ClassVar[str] = "python"
    description: ClassVar[str] = (
        "Run a Python 3 script inside a restrictive macOS sandbox. No network. "
        "CWD is the run's scratch directory; writes elsewhere are denied. "
        "30s timeout."
    )
    input_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {"code": {"type": "string"}},
        "required": ["code"],
    }

    def execute(self, *, code: str, **_: Any) -> ToolResult:
        return self._run(code, [sys.executable], ".py")
