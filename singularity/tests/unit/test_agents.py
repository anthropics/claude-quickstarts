"""Unit testy SingularitySwarm — routing, failover, telemetrie."""
from __future__ import annotations

import pytest

from agents.base import AgentRole
from agents.swarm import SingularitySwarm

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_run_agent_uses_routed_provider(router):
    swarm = SingularitySwarm(router)
    out = await swarm.run_agent(AgentRole.PROGRAMMER, "napiš funkci")
    assert out.provider_used == "gemini"
    assert out.role == AgentRole.PROGRAMMER


@pytest.mark.asyncio
async def test_critic_parses_risk_score(router):
    swarm = SingularitySwarm(router)
    out = await swarm.run_agent(AgentRole.CRITIC, "zhodnoť riziko")
    assert out.risk_score == pytest.approx(0.2)


@pytest.mark.asyncio
async def test_failover_when_primary_fails(claude_mock, gemini_mock):
    from core.router import LLMRouter

    gemini_mock._fail = True   # PROGRAMMER → gemini selže → failover na claude
    router = LLMRouter(claude=claude_mock, gemini=gemini_mock, strategy="static")
    swarm = SingularitySwarm(router)
    out = await swarm.run_agent(AgentRole.PROGRAMMER, "úkol")
    assert out.provider_used == "claude"


@pytest.mark.asyncio
async def test_orchestrate_runs_multiple_agents(router):
    swarm = SingularitySwarm(router)
    outputs = await swarm.orchestrate("úkol", roles=[AgentRole.RESEARCHER, AgentRole.CRITIC])
    assert set(outputs.keys()) == {AgentRole.RESEARCHER, AgentRole.CRITIC}


@pytest.mark.asyncio
async def test_programmer_requires_approval(router):
    swarm = SingularitySwarm(router)
    out = await swarm.run_agent(AgentRole.PROGRAMMER, "deploy")
    assert out.requires_approval is True
