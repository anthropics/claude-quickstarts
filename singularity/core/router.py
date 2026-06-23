"""
Singularity — LLM Router.

Strategie:
  static      — každá AgentRole má pevně přiřazený provider
  failover    — primary provider; při selhání přepne na secondary
  round_robin — střídá providery pro rovnoměrné zatížení

Výchozí přiřazení (static):
  RESEARCHER   → Claude  (hluboké uvažování, fact-checking)
  PROGRAMMER   → Gemini  (velký kontext, generování kódu)
  CRITIC       → Claude  (kritické myšlení, hodnocení rizik)
  PLANNER      → Gemini  (strukturování, dekompozice úkolů)
  COMMUNICATOR → Claude  (přesná formulace výstupů)
"""
from __future__ import annotations

import itertools
import structlog

from agents.base import AgentRole
from providers.base import AbstractLLMProvider

log = structlog.get_logger()

# Výchozí přiřazení role → provider name
_STATIC_ROUTING: dict[AgentRole, str] = {
    AgentRole.RESEARCHER:   "claude",
    AgentRole.PROGRAMMER:   "gemini",
    AgentRole.CRITIC:       "claude",
    AgentRole.PLANNER:      "gemini",
    AgentRole.COMMUNICATOR: "claude",
}


class LLMRouter:
    """
    Inteligentní router mezi LLM providery.
    Při nedostupnosti Gemini automaticky degraduje na Claude-only režim.
    """

    def __init__(
        self,
        claude: AbstractLLMProvider,
        gemini: AbstractLLMProvider | None,
        strategy: str = "static",
    ) -> None:
        self._claude  = claude
        self._gemini  = gemini
        self._strategy = strategy

        # Round-robin cyklus přes dostupné providery
        available = [claude]
        if gemini:
            available.append(gemini)
        self._rr_cycle = itertools.cycle(available)

        log.info(
            "router_init",
            strategy=strategy,
            providers=[p.name for p in available],
        )

    # ── Hlavní API ────────────────────────────────────────────────────────────

    def get_provider(self, role: AgentRole) -> AbstractLLMProvider:
        """Vrátí správný provider pro danou AgentRole dle aktivní strategie."""
        if self._strategy == "round_robin":
            return next(self._rr_cycle)

        # static / failover — prefer assigned provider
        preferred_name = _STATIC_ROUTING.get(role, "claude")
        preferred = self._resolve(preferred_name)
        return preferred

    def get_fallback(self, failed_provider: AbstractLLMProvider) -> AbstractLLMProvider | None:
        """Vrátí náhradní provider (failover strategie)."""
        if failed_provider.name == "claude" and self._gemini:
            log.warning("router_failover", from_="claude", to="gemini")
            return self._gemini
        if failed_provider.name == "gemini":
            log.warning("router_failover", from_="gemini", to="claude")
            return self._claude
        return None

    def all_providers(self) -> list[AbstractLLMProvider]:
        providers = [self._claude]
        if self._gemini:
            providers.append(self._gemini)
        return providers

    def set_strategy(self, strategy: str) -> None:
        if strategy not in ("static", "round_robin", "failover"):
            raise ValueError(f"Neznámá strategie: {strategy!r}")
        self._strategy = strategy
        log.info("router_strategy_changed", strategy=strategy)

    @property
    def strategy(self) -> str:
        return self._strategy

    # ── Privátní ──────────────────────────────────────────────────────────────

    def _resolve(self, name: str) -> AbstractLLMProvider:
        if name == "gemini" and self._gemini:
            return self._gemini
        return self._claude   # fallback vždy na Claude
