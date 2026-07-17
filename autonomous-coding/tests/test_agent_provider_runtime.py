from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import agent


def test_run_phase_session_openai_dispatches_to_codex_cli(monkeypatch, tmp_path: Path) -> None:
    calls: dict[str, object] = {}

    async def fake_run_codex_cli_phase(
        project_dir: Path,
        model: str,
        prompt: str,
        phase: str,
        auth_mode: str = "api_key",
    ) -> str:
        calls["project_dir"] = project_dir
        calls["model"] = model
        calls["prompt"] = prompt
        calls["phase"] = phase
        calls["auth_mode"] = auth_mode
        return "openai response"

    monkeypatch.setattr(agent, "run_codex_cli_phase", fake_run_codex_cli_phase)

    result = asyncio.run(
        agent.run_phase_session(
            project_dir=tmp_path,
            model="gpt-5-codex",
            prompt="Do the work",
            phase="builder",
            provider="openai",
            auth_mode="cli",
        )
    )

    assert result == "openai response"
    assert calls == {
        "project_dir": tmp_path,
        "model": "gpt-5-codex",
        "prompt": "Do the work",
        "phase": "builder",
        "auth_mode": "cli",
    }


def test_run_phase_session_openai_rejects_shared_client(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="does not support shared client sessions"):
        asyncio.run(
            agent.run_phase_session(
                project_dir=tmp_path,
                model="gpt-5-codex",
                prompt="Do the work",
                phase="builder",
                client=object(),
                provider="openai",
            )
        )
