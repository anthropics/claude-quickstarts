from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

import openai_codex_cli


def _write_fake_codex(
    bin_dir: Path,
    args_file: Path,
    token_file: Path,
) -> Path:
    if os.name == "nt":
        fake_codex = bin_dir / "codex.cmd"
        fake_codex.write_text(
            "@echo off\n"
            f'echo %* > "{args_file}"\n'
            f'echo %CODEX_API_KEY% > "{token_file}"\n'
            'echo {"type":"assistant","text":"hello "}\n'
            'echo {"type":"assistant","text":"world"}\n'
        )
        return fake_codex

    fake_codex = bin_dir / "codex"
    fake_codex.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$*\" > \"{args_file}\"\n"
        f"printf '%s\\n' \"$CODEX_API_KEY\" > \"{token_file}\"\n"
        "printf '%s\\n' '{\"type\":\"assistant\",\"text\":\"hello \"}'\n"
        "printf '%s\\n' '{\"type\":\"assistant\",\"text\":\"world\"}'\n"
    )
    fake_codex.chmod(0o755)
    return fake_codex


def test_run_codex_cli_phase_requires_git_repository(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CODEX_API_KEY", "test-key")

    with pytest.raises(RuntimeError, match="requires a Git repository"):
        asyncio.run(
            openai_codex_cli.run_codex_cli_phase(
                project_dir=tmp_path,
                model="gpt-5-codex",
                prompt="Implement the feature",
                phase="builder",
                auth_mode="api_key",
            )
        )


def test_run_codex_cli_phase_collects_json_output(monkeypatch, tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    args_file = tmp_path / "codex-args.txt"
    token_file = tmp_path / "codex-token.txt"
    fake_codex = _write_fake_codex(bin_dir, args_file, token_file)

    monkeypatch.setenv("CODEX_BIN", str(fake_codex))
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.delenv("CODEX_API_KEY", raising=False)
    monkeypatch.setattr(openai_codex_cli, "_ensure_git_repository", lambda project_dir: None)

    result = asyncio.run(
        openai_codex_cli.run_codex_cli_phase(
            project_dir=tmp_path,
            model="gpt-5-codex",
            prompt="Implement the feature",
            phase="builder",
            auth_mode="api_key",
        )
    )

    assert result == "hello world"
    assert "exec --json --model gpt-5-codex" in args_file.read_text()
    assert token_file.read_text().strip() == "openai-test-key"
