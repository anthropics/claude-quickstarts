"""Check CLI iteration limits without starting an agent or calling an API."""

import runpy
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock

import pytest


@pytest.mark.parametrize("limit", [None, "1", "3", "0", "-1", "-10"])
def test_iteration_limit(monkeypatch, capsys, limit):
    agent = ModuleType("agent")
    runner = AsyncMock()
    agent.run_autonomous_agent = runner
    monkeypatch.setitem(sys.modules, "agent", agent)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "unused-test-key")
    args = [] if limit is None else ["--max-iterations", limit]
    monkeypatch.setattr(sys, "argv", ["autonomous_agent_demo.py", *args])
    script = Path(__file__).with_name("autonomous_agent_demo.py")

    if limit is not None and int(limit) <= 0:
        with pytest.raises(SystemExit) as error:
            runpy.run_path(str(script), run_name="__main__")
        assert error.value.code == 2
        assert "positive integer" in capsys.readouterr().err
        runner.assert_not_called()
    else:
        runpy.run_path(str(script), run_name="__main__")
        runner.assert_awaited_once()
        assert runner.call_args.kwargs["max_iterations"] == (
            None if limit is None else int(limit)
        )
