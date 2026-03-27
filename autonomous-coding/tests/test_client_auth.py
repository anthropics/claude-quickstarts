from __future__ import annotations

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
