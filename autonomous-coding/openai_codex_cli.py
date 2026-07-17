"""OpenAI Codex CLI runtime adapter for autonomous coding phases."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path

from client import validate_auth_configuration
from provider_resolution import AuthMode


def _resolve_codex_command() -> list[str]:
    """Resolve the Codex CLI executable command."""
    codex_bin = os.environ.get("CODEX_BIN", "codex")
    return [codex_bin]


def _prepare_codex_environment(auth_mode: AuthMode) -> dict[str, str]:
    """Return environment variables for Codex CLI execution."""
    env = os.environ.copy()
    api_key = env.get("CODEX_API_KEY") or env.get("OPENAI_API_KEY")

    if auth_mode == "api_key" and not api_key:
        raise RuntimeError("OpenAI/Codex execution requires CODEX_API_KEY or OPENAI_API_KEY.")

    if api_key:
        # Normalize the child process environment to the Codex-specific variable.
        env["CODEX_API_KEY"] = api_key

    return env


def _ensure_git_repository(project_dir: Path) -> None:
    """Fail fast when the target project directory is not a Git repository."""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError("Git is required to run the OpenAI/Codex provider.") from exc

    if completed.returncode != 0 or completed.stdout.strip().lower() != "true":
        raise RuntimeError(
            f"OpenAI/Codex provider requires a Git repository at {project_dir}."
        )


def _build_codex_exec_command(model: str, prompt: str) -> list[str]:
    """Build the non-interactive Codex CLI command."""
    command = [*_resolve_codex_command(), "exec", "--json"]
    if model:
        command.extend(["--model", model])
    command.append(prompt)
    return command


def _collect_text_fragments(payload: object, fragments: list[str]) -> None:
    """Collect likely assistant text fragments from a JSON payload."""
    if isinstance(payload, dict):
        output_text = payload.get("output_text")
        text = payload.get("text")
        content = payload.get("content")

        if isinstance(output_text, str) and output_text:
            fragments.append(output_text)
        if isinstance(text, str) and text:
            fragments.append(text)
        if isinstance(content, str) and content:
            fragments.append(content)

        for key, value in payload.items():
            if key in {"output_text", "text", "content"} and isinstance(value, str):
                continue
            _collect_text_fragments(value, fragments)
        return

    if isinstance(payload, list):
        for item in payload:
            _collect_text_fragments(item, fragments)


def _extract_response_text(stdout: str) -> str:
    """Parse JSONL stdout into plain response text."""
    fragments: list[str] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        _collect_text_fragments(payload, fragments)

    rendered = "".join(fragments).strip()
    if rendered:
        return rendered
    return stdout.strip()


async def run_codex_cli_phase(
    project_dir: Path,
    model: str,
    prompt: str,
    phase: str,
    auth_mode: AuthMode = "api_key",
) -> str:
    """Execute a phase prompt through Codex CLI and return plain-text output."""
    del phase
    validate_auth_configuration(auth_mode, provider="openai")
    _ensure_git_repository(project_dir)
    command = _build_codex_exec_command(model, prompt)
    env = _prepare_codex_environment(auth_mode)

    completed = await asyncio.to_thread(
        subprocess.run,
        command,
        cwd=str(project_dir),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    stdout = completed.stdout
    stderr = completed.stderr

    if completed.returncode != 0:
        details = stderr.strip() or stdout.strip() or "Codex CLI execution failed."
        raise RuntimeError(details)

    response = _extract_response_text(stdout)
    if not response:
        raise RuntimeError("Codex CLI returned an empty response.")
    return response
