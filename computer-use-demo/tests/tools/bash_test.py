import asyncio
import os
import shlex
import signal
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from computer_use_demo.tools.bash import BashTool20241022, BashTool20250124, ToolError


@pytest_asyncio.fixture(params=[BashTool20241022, BashTool20250124])
async def bash_tool(
    request: pytest.FixtureRequest,
) -> AsyncIterator[BashTool20250124]:
    tool = request.param()
    try:
        yield tool
    finally:
        if tool._session is not None:
            process = tool._session._process
            if process.returncode is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            await asyncio.wait_for(process.communicate(), timeout=2)


@pytest.mark.asyncio
async def test_bash_tool_restart(bash_tool):
    result = await bash_tool(restart=True)
    assert result.system == "tool has been restarted."

    # Verify the tool can be used after restart
    result = await bash_tool(command="echo 'Hello after restart'")
    assert "Hello after restart" in result.output


@pytest.mark.asyncio
async def test_bash_tool_run_command(bash_tool):
    result = await bash_tool(command="echo 'Hello, World!'")
    assert result.output.strip() == "Hello, World!"
    assert result.error == ""


@pytest.mark.asyncio
async def test_bash_tool_no_command(bash_tool):
    with pytest.raises(ToolError, match="no command provided."):
        await bash_tool()


@pytest.mark.asyncio
async def test_bash_tool_session_creation(bash_tool):
    result = await bash_tool(command="echo 'Session created'")
    assert bash_tool._session is not None
    assert "Session created" in result.output


@pytest.mark.asyncio
async def test_bash_tool_session_reuse(bash_tool):
    result1 = await bash_tool(command="echo 'First command'")
    result2 = await bash_tool(command="echo 'Second command'")

    assert "First command" in result1.output
    assert "Second command" in result2.output


@pytest.mark.asyncio
async def test_bash_tool_session_error(bash_tool):
    result = await bash_tool(command="invalid_command_that_does_not_exist")
    assert "command not found" in result.error


@pytest.mark.asyncio
async def test_bash_tool_non_zero_exit(bash_tool):
    result = await bash_tool(command="bash -c 'exit 1'")
    assert result.error.strip() == ""
    assert result.output.strip() == ""


@pytest.mark.asyncio
async def test_bash_tool_timeout(bash_tool):
    await bash_tool(command="echo 'Hello, World!'")
    bash_tool._session._timeout = 0.1  # Set a very short timeout for testing
    with pytest.raises(
        ToolError,
        match="timed out: bash has not returned in 0.1 seconds and must be restarted",
    ):
        await bash_tool(command="sleep 1")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "repetitions"),
    [("x", 262144), ("世界", 65536)],
    ids=["ascii", "unicode"],
)
@pytest.mark.parametrize("stream", ["stdout", "stderr", "both"])
async def test_bash_tool_large_output(
    bash_tool: BashTool20250124, text: str, repetitions: int, stream: str
) -> None:
    await bash_tool(command="printf ready")
    assert bash_tool._session is not None
    session = bash_tool._session
    session._timeout = 2.0
    output = text * repetitions
    program = "import sys; "
    if stream in {"stdout", "both"}:
        program += f"sys.stdout.write({text!r} * {repetitions}); "
    if stream in {"stderr", "both"}:
        program += f"sys.stderr.write({text!r} * {repetitions}); "
    command = f"{shlex.quote(sys.executable)} -c {shlex.quote(program)}"

    result = await bash_tool(command=command)
    assert result.output == (output if stream in {"stdout", "both"} else "")
    assert result.error == (output if stream in {"stderr", "both"} else "")

    result = await bash_tool(command="printf next")
    assert result.output == "next"
    assert result.error == ""


@pytest.mark.asyncio
async def test_bash_tool_timeout_cleans_readers(bash_tool: BashTool20250124) -> None:
    await bash_tool(command="printf ready")
    assert bash_tool._session is not None
    bash_tool._session._timeout = 0.05
    original_tasks = asyncio.all_tasks()

    with pytest.raises(ToolError, match="timed out"):
        await bash_tool(command="sleep 1")
    assert asyncio.all_tasks() == original_tasks

    with pytest.raises(ToolError, match="must be restarted"):
        await bash_tool(command="printf next")


@pytest.mark.asyncio
async def test_bash_tool_literal_sentinel(bash_tool: BashTool20250124) -> None:
    result = await bash_tool(command="printf '<<exit>>'; printf '<<exit>>' >&2")
    assert result.output == "<<exit>>"
    assert result.error == "<<exit>>"


@pytest.mark.asyncio
async def test_bash_tool_redirected_stderr(
    bash_tool: BashTool20250124, tmp_path: Path
) -> None:
    destination = tmp_path / "stderr.txt"
    result = await bash_tool(
        command=f"exec 2>{shlex.quote(str(destination))}; printf redirected >&2"
    )
    assert result.output == ""
    assert result.error == ""
    assert destination.read_text() == "redirected"

    result = await bash_tool(command="printf next")
    assert result.output == "next"
    assert result.error == ""
