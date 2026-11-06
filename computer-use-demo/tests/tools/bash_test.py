import pytest

from computer_use_demo.tools.bash import BashTool20241022, BashTool20250124, ToolError


@pytest.fixture(params=[BashTool20241022, BashTool20250124])
def bash_tool(request):
    return request.param()


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
    assert result.exit_code == 1
    assert result.error.strip() == ""
    assert result.output.strip() == ""


@pytest.mark.asyncio
async def test_bash_tool_reports_the_command_exit_code(bash_tool):
    result = await bash_tool(command="echo ok")
    assert result.exit_code == 0
    assert result.output.strip() == "ok"

    result = await bash_tool(command="(exit 7)")
    assert result.exit_code == 7

    result = await bash_tool(command="echo partial output; false")
    assert result.exit_code == 1
    assert result.output.strip() == "partial output"


@pytest.mark.asyncio
async def test_bash_tool_stderr_on_success_keeps_a_zero_exit_code(bash_tool):
    result = await bash_tool(command="echo warn >&2; echo ok")
    assert result.exit_code == 0
    assert result.output.strip() == "ok"
    assert result.error.strip() == "warn"


@pytest.mark.asyncio
async def test_bash_tool_exit_code_does_not_leak_into_output(bash_tool):
    result = await bash_tool(command="printf 'no trailing newline'")
    assert result.exit_code == 0
    assert result.output == "no trailing newline"
    assert "<<exit>>" not in result.output


@pytest.mark.asyncio
async def test_bash_tool_output_containing_the_sentinel_is_kept(bash_tool):
    sentinel = bash_tool._session._sentinel if bash_tool._session else "<<exit>>"
    result = await bash_tool(command=f"echo 'see {sentinel} marker'; echo done")
    assert result.exit_code == 0
    assert result.output.strip() == f"see {sentinel} marker\ndone"

    result = await bash_tool(command=f"echo '{sentinel} 5'; (exit 3)")
    assert result.exit_code == 3
    assert result.output.strip() == f"{sentinel} 5"


@pytest.mark.asyncio
async def test_bash_tool_timeout(bash_tool):
    await bash_tool(command="echo 'Hello, World!'")
    bash_tool._session._timeout = 0.1  # Set a very short timeout for testing
    with pytest.raises(
        ToolError,
        match="timed out: bash has not returned in 0.1 seconds and must be restarted",
    ):
        await bash_tool(command="sleep 1")
