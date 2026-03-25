"""Claude SDK client configuration for autonomous coding harness."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

from claude_code_sdk import ClaudeCodeOptions, ClaudeSDKClient
from claude_code_sdk.types import HookMatcher

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


def _browser_config(preferred: str = "playwright") -> tuple[list[str], dict]:
    """Return allowed browser tools and MCP server config.

    Playwright is preferred; Puppeteer is retained as fallback.
    """
    if preferred == "puppeteer":
        return PUPPETEER_TOOLS, {
            "puppeteer": {"command": "npx", "args": ["puppeteer-mcp-server"]}
        }

    return PLAYWRIGHT_TOOLS, {
        "playwright": {"command": "npx", "args": ["@playwright/mcp@latest"]},
        "puppeteer": {"command": "npx", "args": ["puppeteer-mcp-server"]},
    }


def create_client(
    project_dir: Path,
    model: str,
    phase: str,
    browser_provider: str = "playwright",
) -> ClaudeSDKClient:
    """Create a Claude Agent SDK client with security and phase-aware tooling."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable not set.\n"
            "Get your API key from: https://console.anthropic.com/"
        )

    browser_tools, mcp_servers = _browser_config(browser_provider)
    allowed_tools = [*BUILTIN_TOOLS]
    if phase in {"builder", "evaluator", "orchestrator"}:
        allowed_tools.extend(browser_tools)

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
                *browser_tools,
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
