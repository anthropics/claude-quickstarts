"""
Singularity — Pytest fixtures.

Poskytuje mock LLM providery (bez API klíčů) a mock router/swarm,
takže unit testy běží plně offline a deterministicky.
"""
from __future__ import annotations

import pytest

from agents.base import AgentRole
from core.limiter import ProviderRateLimiter
from core.router import LLMRouter
from providers.base import AbstractLLMProvider, LLMResponse


class MockProvider(AbstractLLMProvider):
    """Deterministický mock provider pro testy."""

    def __init__(
        self,
        name: str,
        *,
        cost_per_1k: float = 0.001,
        typical_latency_ms: float = 100.0,
        quality_rank: int = 1,
        fail: bool = False,
    ) -> None:
        super().__init__()
        self.name = name
        self.cost_per_1k = cost_per_1k
        self.typical_latency_ms = typical_latency_ms
        self.quality_rank = quality_rank
        self._fail = fail
        self.call_count = 0

    async def ainvoke(self, messages: list) -> LLMResponse:
        self.call_count += 1
        if self._fail:
            raise ConnectionError(f"{self.name} simulované selhání")
        return LLMResponse(
            content=f"[{self.name}] odpověď RISK_SCORE: 0.2",
            provider=self.name,
            model=f"{self.name}-mock",
            tokens_used=42,
            latency_ms=self.typical_latency_ms,
        )

    async def health_check(self) -> bool:
        return not self._fail


@pytest.fixture
def claude_mock() -> MockProvider:
    return MockProvider("claude", cost_per_1k=0.003, typical_latency_ms=1800.0, quality_rank=1)


@pytest.fixture
def gemini_mock() -> MockProvider:
    return MockProvider("gemini", cost_per_1k=0.0005, typical_latency_ms=900.0, quality_rank=2)


@pytest.fixture
def router(claude_mock, gemini_mock) -> LLMRouter:
    return LLMRouter(claude=claude_mock, gemini=gemini_mock, strategy="static")


@pytest.fixture
def router_no_gemini(claude_mock) -> LLMRouter:
    return LLMRouter(claude=claude_mock, gemini=None, strategy="static")


@pytest.fixture
def limiter() -> ProviderRateLimiter:
    return ProviderRateLimiter()


@pytest.fixture
def all_roles() -> list[AgentRole]:
    return list(AgentRole)
