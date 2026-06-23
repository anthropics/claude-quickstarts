"""
Singularity — LLM Router.

Strategie:
  static            — každá AgentRole má pevně přiřazený provider
  failover          — primary; při selhání/cooldownu přepne na druhý
  round_robin       — střídá dostupné providery (load balancing)
  cost_optimized    — nejlevnější dostupný provider (cost_per_1k)
  latency_optimized — nejrychlejší dostupný provider (typical_latency_ms)
  quality_first     — nejvýše hodnocený dostupný provider (quality_rank)

Výchozí static přiřazení:
  RESEARCHER → Claude · PROGRAMMER → Gemini · CRITIC → Claude
  PLANNER → Gemini · COMMUNICATOR → Claude

Self-healing: provideři v cooldownu (is_available() == False) jsou z výběru
vyloučeni; pokud nezbude žádný, padáme zpět na Claude.
"""
from __future__ import annotations

import itertools
import structlog

from agents.base import AgentRole
from core import telemetry
from providers.base import AbstractLLMProvider

log = structlog.get_logger()

VALID_STRATEGIES = (
    "static",
    "failover",
    "round_robin",
    "cost_optimized",
    "latency_optimized",
    "quality_first",
)

_STATIC_ROUTING: dict[AgentRole, str] = {
    AgentRole.RESEARCHER:   "claude",
    AgentRole.PROGRAMMER:   "gemini",
    AgentRole.CRITIC:       "claude",
    AgentRole.PLANNER:      "gemini",
    AgentRole.COMMUNICATOR: "claude",
}


class LLMRouter:
    """Inteligentní router mezi LLM providery se self-healingem."""

    def __init__(
        self,
        claude: AbstractLLMProvider,
        gemini: AbstractLLMProvider | None,
        strategy: str = "static",
    ) -> None:
        if strategy not in VALID_STRATEGIES:
            raise ValueError(f"Neznámá strategie: {strategy!r}")

        self._claude = claude
        self._gemini = gemini
        self._strategy = strategy
        self._rr_cycle = itertools.cycle(self.all_providers())

        log.info("router_init", strategy=strategy, providers=[p.name for p in self.all_providers()])

    # ── Hlavní API ────────────────────────────────────────────────────────────

    def get_provider(self, role: AgentRole) -> AbstractLLMProvider:
        """Vybere provider pro danou roli dle aktivní strategie (jen dostupné)."""
        available = self.available_providers()
        if not available:
            log.warning("no_available_providers_fallback_claude")
            return self._claude

        if self._strategy == "round_robin":
            return self._next_available_rr(available)
        if self._strategy == "cost_optimized":
            return min(available, key=lambda p: p.cost_per_1k)
        if self._strategy == "latency_optimized":
            return min(available, key=lambda p: p.typical_latency_ms)
        if self._strategy == "quality_first":
            return min(available, key=lambda p: p.quality_rank)

        # static / failover — preferuj přiřazený provider, jinak první dostupný
        preferred = self._resolve(_STATIC_ROUTING.get(role, "claude"))
        if preferred.is_available():
            return preferred
        return available[0]

    def get_fallback(self, failed: AbstractLLMProvider) -> AbstractLLMProvider | None:
        """Náhradní dostupný provider po selhání (failover)."""
        for candidate in self.all_providers():
            if candidate.name != failed.name and candidate.is_available():
                telemetry.record_switch(failed.name, candidate.name)
                return candidate
        return None

    def all_providers(self) -> list[AbstractLLMProvider]:
        providers = [self._claude]
        if self._gemini is not None:
            providers.append(self._gemini)
        return providers

    def available_providers(self) -> list[AbstractLLMProvider]:
        return [p for p in self.all_providers() if p.is_available()]

    def set_strategy(self, strategy: str) -> None:
        if strategy not in VALID_STRATEGIES:
            raise ValueError(f"Neznámá strategie: {strategy!r}")
        self._strategy = strategy
        log.info("router_strategy_changed", strategy=strategy)

    @property
    def strategy(self) -> str:
        return self._strategy

    @property
    def gemini_enabled(self) -> bool:
        return self._gemini is not None

    # ── Privátní ──────────────────────────────────────────────────────────────

    def _resolve(self, name: str) -> AbstractLLMProvider:
        if name == "gemini" and self._gemini is not None:
            return self._gemini
        return self._claude

    def _next_available_rr(self, available: list[AbstractLLMProvider]) -> AbstractLLMProvider:
        names = {p.name for p in available}
        for _ in range(len(self.all_providers()) * 2):
            candidate = next(self._rr_cycle)
            if candidate.name in names:
                return candidate
        return available[0]
