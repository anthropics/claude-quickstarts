from __future__ import annotations

import json
from pathlib import Path

import pytest

import client


def test_has_claude_cli_credentials_detects_token_env(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_CODE_AUTH_TOKEN", "token")
    assert client._has_claude_cli_credentials() is True


def test_has_claude_cli_credentials_detects_credentials_file(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".anthropic").mkdir(parents=True)
    (home / ".anthropic" / "credentials.json").write_text('{"ok": true}')
    monkeypatch.setattr(Path, "home", lambda: home)

    monkeypatch.delenv("CLAUDE_CODE_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("CLAUDE_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)

    assert client._has_claude_cli_credentials() is True


def test_validate_auth_configuration_api_key_requires_env(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY environment variable not set"):
        client.validate_auth_configuration("api_key")


def test_validate_auth_configuration_cli_requires_credentials(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)

    monkeypatch.delenv("CLAUDE_CODE_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("CLAUDE_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    with pytest.raises(ValueError, match="Claude CLI credentials were not detected"):
        client.validate_auth_configuration("cli")


def test_validate_auth_configuration_auto_accepts_api_key(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("CLAUDE_CODE_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("CLAUDE_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)

    client.validate_auth_configuration("auto")


def test_validate_auth_configuration_openai_api_key_requires_env(monkeypatch) -> None:
    monkeypatch.delenv("CODEX_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="CODEX_API_KEY or OPENAI_API_KEY"):
        client.validate_auth_configuration("api_key", provider="openai")


def test_validate_auth_configuration_openai_cli_requires_cached_login(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)

    with pytest.raises(ValueError, match="Codex CLI credentials were not detected"):
        client.validate_auth_configuration("cli", provider="openai")


def test_validate_auth_configuration_openai_cli_accepts_auth_cache(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    (home / ".codex" / "auth.json").write_text('{"access_token": "ok"}')
    monkeypatch.setattr(Path, "home", lambda: home)

    client.validate_auth_configuration("cli", provider="openai")


def test_validate_auth_configuration_openai_auto_accepts_codex_api_key(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setenv("CODEX_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    client.validate_auth_configuration("auto", provider="openai")


def test_browser_config_prefers_playwright_headless_by_default() -> None:
    tools, servers = client._browser_config()
    assert tools == client.PLAYWRIGHT_TOOLS
    assert servers["playwright"]["command"] == "npx"
    assert servers["playwright"]["args"] == ["@playwright/mcp@latest", "--headless"]
    assert "puppeteer" in servers


def test_browser_config_allows_explicit_puppeteer_fallback() -> None:
    tools, servers = client._browser_config("puppeteer")
    assert tools == client.PUPPETEER_TOOLS
    assert servers == {"puppeteer": {"command": "npx", "args": ["puppeteer-mcp-server"]}}


class _CapturingClient:
    def __init__(self, *, options):
        self.options = options


def test_create_client_writes_settings_and_keeps_planner_browserless(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(client, "validate_auth_configuration", lambda *args, **kwargs: None)
    monkeypatch.setattr(client, "ClaudeSDKClient", _CapturingClient)

    created = client.create_client(tmp_path, model="m", phase="planner")
    settings = json.loads((tmp_path / ".claude_settings.json").read_text(encoding="utf-8"))
    allowed_tools = list(created.options.allowed_tools)

    assert allowed_tools == client.BUILTIN_TOOLS
    assert client.PLAYWRIGHT_TOOLS[0] not in allowed_tools
    assert client.PLAYWRIGHT_TOOLS[0] not in settings["permissions"]["allow"]
    assert settings["permissions"]["defaultMode"] == "acceptEdits"
    assert settings["sandbox"]["enabled"] is True
    assert created.options.cwd == str(tmp_path.resolve())
    assert created.options.settings == str((tmp_path / ".claude_settings.json").resolve())


@pytest.mark.parametrize("phase", ["builder", "evaluator", "orchestrator"])
def test_create_client_enables_browser_tools_for_browser_phases(monkeypatch, tmp_path: Path, phase: str) -> None:
    monkeypatch.setattr(client, "validate_auth_configuration", lambda *args, **kwargs: None)
    monkeypatch.setattr(client, "ClaudeSDKClient", _CapturingClient)

    created = client.create_client(tmp_path, model="m", phase=phase)
    settings = json.loads((tmp_path / ".claude_settings.json").read_text(encoding="utf-8"))
    allowed_tools = list(created.options.allowed_tools)

    for tool in client.PLAYWRIGHT_TOOLS:
        assert tool in allowed_tools
        assert tool in settings["permissions"]["allow"]

    assert settings["sandbox"]["enabled"] is True
