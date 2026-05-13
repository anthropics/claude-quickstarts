import sys

import pytest

from computer_use.tools.shell import BashTool, PythonTool

darwin_only = pytest.mark.skipif(sys.platform != "darwin", reason="sandbox-exec is macOS")


@darwin_only
def test_bash_echo():
    res = BashTool().execute(command="echo hello")
    assert not res.is_error, res.error
    assert res.output is not None
    assert "hello" in res.output


@darwin_only
def test_python_print():
    res = PythonTool().execute(code="print(1 + 1)")
    assert not res.is_error, res.error
    assert res.output is not None
    assert res.output.strip().startswith("2")


@darwin_only
def test_sandbox_denies_home_write():
    res = BashTool().execute(command="touch ~/should_not_exist_cu_demo")
    assert res.is_error


@darwin_only
def test_sandbox_denies_secret_read(tmp_path):
    """Credential paths under $HOME and any .env file are unreadable."""
    from pathlib import Path

    ssh = Path.home() / ".ssh"
    if not ssh.exists() or not any(ssh.iterdir()):
        pytest.skip("~/.ssh empty")
    res = BashTool().execute(command=f"ls {ssh}")
    assert res.is_error, res.output

    env = tmp_path / ".env"
    env.write_text("SECRET=1")
    res2 = BashTool().execute(command=f"cat {env}")
    assert res2.is_error, res2.output


@darwin_only
def test_output_truncated():
    from constants import cfg

    res = PythonTool().execute(code='print("x" * 200_000)')
    assert not res.is_error, res.error
    assert res.output is not None
    assert len(res.output) <= cfg.max_shell_output_bytes + 100
    assert "[output truncated" in res.output
