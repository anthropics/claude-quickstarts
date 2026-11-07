import asyncio
import os
from typing import Any, Literal
from uuid import uuid4

from .base import BaseAnthropicTool, CLIResult, ToolError, ToolResult


async def _read_until_sentinel(stream: asyncio.StreamReader, sentinel: bytes) -> bytes:
    """Read a stream through the command's completion marker."""
    output = bytearray()
    while True:
        chunk = await stream.read(65536)
        if not chunk:
            raise ToolError("bash output stream closed before command completion")
        output.extend(chunk)
        if sentinel in output:
            return bytes(output[: output.index(sentinel)])


class _BashSession:
    """A session of a bash shell."""

    _started: bool
    _process: asyncio.subprocess.Process

    command: str = "/bin/bash"
    _timeout: float = 120.0  # seconds
    _sentinel: str = "<<exit>>"
    _stderr_completion_fd: int = 9

    def __init__(self):
        self._started = False
        self._timed_out = False

    async def start(self):
        if self._started:
            return

        self._process = await asyncio.create_subprocess_shell(
            f"{self.command} {self._stderr_completion_fd}>&2",
            preexec_fn=os.setsid,
            shell=True,
            bufsize=0,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self._started = True

    def stop(self):
        """Terminate the bash shell."""
        if not self._started:
            raise ToolError("Session has not started.")
        if self._process.returncode is not None:
            return
        self._process.terminate()

    async def run(self, command: str):
        """Execute a command in the bash shell."""
        if not self._started:
            raise ToolError("Session has not started.")
        if self._process.returncode is not None:
            return ToolResult(
                system="tool must be restarted",
                error=f"bash has exited with returncode {self._process.returncode}",
            )
        if self._timed_out:
            raise ToolError(
                f"timed out: bash has not returned in {self._timeout} seconds and must be restarted",
            )

        # we know these are not None because we created the process with PIPEs
        assert self._process.stdin
        assert self._process.stdout
        assert self._process.stderr

        # send command to the process
        sentinel = f"{self._sentinel}{uuid4().hex}"
        self._process.stdin.write(
            command.encode()
            + f"; echo '{sentinel}'; echo '{sentinel}' >&{self._stderr_completion_fd}\n".encode()
        )
        await self._process.stdin.drain()

        sentinel_bytes = f"{sentinel}\n".encode()
        readers = [
            asyncio.create_task(_read_until_sentinel(stream, sentinel_bytes))
            for stream in (self._process.stdout, self._process.stderr)
        ]
        try:
            async with asyncio.timeout(self._timeout):
                output, error = await asyncio.gather(*readers)
        except asyncio.TimeoutError:
            self._timed_out = True
            raise ToolError(
                f"timed out: bash has not returned in {self._timeout} seconds and must be restarted",
            ) from None
        finally:
            for reader in readers:
                reader.cancel()
            await asyncio.gather(*readers, return_exceptions=True)

        return CLIResult(
            output=output.decode().removesuffix("\n"),
            error=error.decode().removesuffix("\n"),
        )


class BashTool20250124(BaseAnthropicTool):
    """
    A tool that allows the agent to run bash commands.
    The tool parameters are defined by Anthropic and are not editable.
    """

    _session: _BashSession | None

    api_type: Literal["bash_20250124"] = "bash_20250124"
    name: Literal["bash"] = "bash"

    def __init__(self):
        self._session = None
        super().__init__()

    def to_params(self) -> Any:
        return {
            "type": self.api_type,
            "name": self.name,
        }

    async def __call__(
        self, command: str | None = None, restart: bool = False, **kwargs
    ):
        if restart:
            if self._session:
                self._session.stop()
            self._session = _BashSession()
            await self._session.start()

            return ToolResult(system="tool has been restarted.")

        if self._session is None:
            self._session = _BashSession()
            await self._session.start()

        if command is not None:
            return await self._session.run(command)

        raise ToolError("no command provided.")


class BashTool20241022(BashTool20250124):
    api_type: Literal["bash_20250124"] = "bash_20250124"  # pyright: ignore[reportIncompatibleVariableOverride]
