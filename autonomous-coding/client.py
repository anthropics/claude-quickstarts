"""Claude SDK client configuration for autonomous coding harness."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

from claude_code_sdk import ClaudeCodeOptions, ClaudeSDKClient
from claude_code_sdk.types import HookMatcher

from provider_resolution import AuthMode, Provider
from security import bash_security_hook

BUILTIN_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash"]

PLAYWRIGHT_TOOLS = [
    "mcp__playwright__browser_navigate",
    "mcp__playwright__browser_click",
    "mcp__playwright__browser_type",
    "mcp__playwright__browser_snapshot",
    "mcp__playwright__browser_take_screenshot",
]

PUPPETEER_TOOLS = [
    "mcp__puppeteer__puppeteer_navigate",
    "mcp__puppeteer__puppeteer_screenshot",
    "mcp__puppeteer__puppeteer_click",
    "mcp__puppeteer__puppeteer_fill",
    "mcp__puppeteer__puppeteer_select",
    "mcp__puppeteer__puppeteer_hover",
    "mcp__puppeteer__puppeteer_evaluate",
]

def _has_claude_cli_credentials() -> bool:
    """Best-effort detection for Claude CLI credentials.

    The SDK remains the source of truth; this check is used for clear
    preflight errors before client startup.
    """
    cli_token_env_vars = (
        "CLAUDE_CODE_AUTH_TOKEN",
        "CLAUDE_AUTH_TOKEN",
        "ANTHROPIC_AUTH_TOKEN",
    )
    if any(os.environ.get(var) for var in cli_token_env_vars):
        return True

    home = Path.home()
    candidate_files = (
        home / ".anthropic" / "credentials.json",
        home / ".config" / "claude" / "credentials.json",
        home / ".claude" / "credentials.json",
    )
    if any(path.exists() for path in candidate_files):
        return True

    anthropic_dir = home / ".anthropic"
    if anthropic_dir.exists():
        for candidate in anthropic_dir.glob("*.json"):
            stem = candidate.stem.lower()
            if "credential" in stem or "auth" in stem:
                return True
    return False


def _has_openai_cli_credentials() -> bool:
    """Best-effort detection for Codex CLI cached authentication."""
    auth_cache = Path.home() / ".codex" / "auth.json"
    return auth_cache.exists()


def _has_openai_api_key() -> bool:
    """Return whether an OpenAI/Codex API key is configured."""
    return bool(os.environ.get("CODEX_API_KEY") or os.environ.get("OPENAI_API_KEY"))


def validate_auth_configuration(auth_mode: AuthMode, provider: Provider = "claude") -> None:
    """Validate selected auth mode with explicit, user-facing errors."""
    if auth_mode not in {"api_key", "cli", "auto"}:
        raise ValueError(f"Unsupported auth_mode '{auth_mode}'. Expected one of: api_key, cli, auto.")

    if provider == "openai":
        has_api_key = _has_openai_api_key()
        has_cli_credentials = _has_openai_cli_credentials()

        if auth_mode == "api_key" and not has_api_key:
            raise ValueError(
                "OpenAI/Codex API key not detected.\n"
                "Set CODEX_API_KEY or OPENAI_API_KEY before starting."
            )

        if auth_mode == "cli" and not has_cli_credentials:
            raise ValueError(
                "Codex CLI credentials were not detected.\n"
                "Run `codex login` (or provide a cached auth session) before starting."
            )

        if auth_mode == "auto" and not (has_api_key or has_cli_credentials):
            raise ValueError(
                "No authentication method detected for OpenAI/Codex.\n"
                "Set CODEX_API_KEY or OPENAI_API_KEY, or authenticate with Codex CLI (`codex login`)."
            )
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    has_cli_credentials = _has_claude_cli_credentials()

    if auth_mode == "api_key" and not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable not set.\n"
            "Get your API key from: https://console.anthropic.com/"
        )

    if auth_mode == "cli" and not has_cli_credentials:
        raise ValueError(
            "Claude CLI credentials were not detected.\n"
            "Run `claude login` (or provide CLI auth token/credentials) before starting."
        )

    if auth_mode == "auto" and not (api_key or has_cli_credentials):
        raise ValueError(
            "No authentication method detected.\n"
            "Set ANTHROPIC_API_KEY or authenticate with Claude CLI (`claude login`)."
        )


def _browser_config(preferred: str = "playwright") -> tuple[list[str], dict]:
    """Return allowed browser tools and MCP server config.

    Playwright is preferred and launched headless by default.
    Puppeteer is retained as fallback.
    """
    if preferred == "puppeteer":
        return PUPPETEER_TOOLS, {
            "puppeteer": {"command": "npx", "args": ["puppeteer-mcp-server"]}
        }

    return PLAYWRIGHT_TOOLS, {
        "playwright": {"command": "npx", "args": ["@playwright/mcp@latest", "--headless"]},
        "puppeteer": {"command": "npx", "args": ["puppeteer-mcp-server"]},
    }


def create_client(
    project_dir: Path,
    model: str,
    phase: str,
    browser_provider: str = "playwright",
    auth_mode: AuthMode = "api_key",
    provider: Provider = "claude",
) -> ClaudeSDKClient:
    """Create a Claude Agent SDK client with security and phase-aware tooling."""
    if provider != "claude":
        raise ValueError("create_client only supports the Claude runtime.")

    validate_auth_configuration(auth_mode, provider=provider)

    browser_tools, mcp_servers = _browser_config(browser_provider)
    phase_browser_tools = [*browser_tools] if phase in {"builder", "evaluator", "orchestrator"} else []
    allowed_tools = [*BUILTIN_TOOLS]
    allowed_tools.extend(phase_browser_tools)

    security_settings = {
        "sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True},
        "permissions": {
            "defaultMode": "acceptEdits",
            "allow": [
                "Read(./**)",
                "Write(./**)",
                "Edit(./**)",
                "Glob(./**)",
                "Grep(./**)",
                "Bash(*)",
                *phase_browser_tools,
            ],
        },
    }

    project_dir.mkdir(parents=True, exist_ok=True)
    settings_file = project_dir / ".claude_settings.json"
    rendered_settings = json.dumps(security_settings, indent=2)
    existing_settings = settings_file.read_text() if settings_file.exists() else None
    if existing_settings != rendered_settings:
        settings_file.write_text(rendered_settings)

    return ClaudeSDKClient(
        options=ClaudeCodeOptions(
            model=model,
            system_prompt=(
                "You are an expert software engineer operating in a structured phase harness. "
                "Always write required artifacts and follow security constraints."
            ),
            allowed_tools=allowed_tools,
            mcp_servers=mcp_servers,
            hooks={"PreToolUse": [HookMatcher(matcher="Bash", hooks=[cast(Any, bash_security_hook)])]},
            max_turns=1000,
            cwd=str(project_dir.resolve()),
            settings=str(settings_file.resolve()),
        )
    )
