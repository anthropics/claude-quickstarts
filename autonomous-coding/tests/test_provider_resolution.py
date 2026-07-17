from __future__ import annotations

import pytest

from provider_resolution import AuthMode, resolve_provider_backend


def test_resolve_provider_backend_claude_preserves_sdk_backend() -> None:
    resolved = resolve_provider_backend("claude", "api_key")
    assert resolved.provider == "claude"
    assert resolved.auth_mode == "api_key"
    assert resolved.backend == "claude_sdk"
    assert resolved.capabilities.supports_shared_session is True
    assert resolved.capabilities.requires_git_repo is False


@pytest.mark.parametrize("auth_mode", ["api_key", "cli", "auto"])
def test_resolve_provider_backend_openai_uses_codex_cli_backend(auth_mode: AuthMode) -> None:
    resolved = resolve_provider_backend("openai", auth_mode)
    assert resolved.provider == "openai"
    assert resolved.auth_mode == auth_mode
    assert resolved.backend == "codex_cli"
    assert resolved.capabilities.supports_shared_session is False
    assert resolved.capabilities.requires_git_repo is True
