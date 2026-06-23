"""
Chaos testy — odolnost vůči výpadkům providerů.

Ověřuje, že failover + self-healing + tenacity retry udrží systém funkční
i při vysoké míře selhání jednoho providera.
"""
from __future__ import annotations

import pytest

from agents.base import AgentRole
from agents.swarm import SingularitySwarm
from core.router import LLMRouter
from tests.conftest import MockProvider

pytestmark = pytest.mark.chaos


@pytest.mark.asyncio
async def test_survives_gemini_total_failure(claude_mock):
    """Gemini úplně padá → všechny role musí dojet přes Claude failover."""
    gemini = MockProvider("gemini", fail=True)
    router = LLMRouter(claude=claude_mock, gemini=gemini, strategy="static")
    swarm = SingularitySwarm(router)

    survived = 0
    for role in AgentRole:
        out = await swarm.run_agent(role, "úkol")
        if out.provider_used == "claude":
            survived += 1

    # Všech 5 rolí přežilo přes failover
    assert survived == len(list(AgentRole))


@pytest.mark.asyncio
async def test_cooldown_after_repeated_failures(claude_mock):
    gemini = MockProvider("gemini", fail=True)
    router = LLMRouter(claude=claude_mock, gemini=gemini, strategy="static")
    swarm = SingularitySwarm(router)

    # PROGRAMMER → gemini opakovaně selhává
    for _ in range(gemini.COOLDOWN_THRESHOLD + 1):
        await swarm.run_agent(AgentRole.PROGRAMMER, "úkol")

    assert gemini.is_available() is False


@pytest.mark.asyncio
async def test_orchestrate_partial_failure_does_not_crash(claude_mock):
    """Selhání jednoho agenta nesmí shodit celou orchestraci."""
    gemini = MockProvider("gemini", fail=True)
    router = LLMRouter(claude=claude_mock, gemini=gemini, strategy="round_robin")
    swarm = SingularitySwarm(router)

    outputs = await swarm.orchestrate(
        "úkol", roles=[AgentRole.RESEARCHER, AgentRole.PLANNER, AgentRole.CRITIC]
    )
    # Alespoň některé výstupy projdou (failover na claude)
    assert len(outputs) >= 1
