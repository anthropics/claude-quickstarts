"""Provider/auth resolution for autonomous coding runtimes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Provider = Literal["claude", "openai"]
AuthMode = Literal["api_key", "cli", "auto"]
ResolvedBackend = Literal["claude_sdk", "codex_cli"]


@dataclass(frozen=True)
class ProviderCapabilities:
    supports_shared_session: bool
    requires_git_repo: bool


@dataclass(frozen=True)
class ResolvedProviderBackend:
    provider: Provider
    auth_mode: AuthMode
    backend: ResolvedBackend
    capabilities: ProviderCapabilities


def resolve_provider_backend(provider: Provider, auth_mode: AuthMode) -> ResolvedProviderBackend:
    """Resolve the concrete runtime backend for a provider/auth pair."""
    if provider == "claude":
        return ResolvedProviderBackend(
            provider=provider,
            auth_mode=auth_mode,
            backend="claude_sdk",
            capabilities=ProviderCapabilities(
                supports_shared_session=True,
                requires_git_repo=False,
            ),
        )

    return ResolvedProviderBackend(
        provider=provider,
        auth_mode=auth_mode,
        backend="codex_cli",
        capabilities=ProviderCapabilities(
            supports_shared_session=False,
            requires_git_repo=True,
        ),
    )
