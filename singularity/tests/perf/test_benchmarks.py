"""
Výkonnostní testy — režie routingu a orchestrace s mock providery.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from agents.base import AgentRole
from agents.swarm import SingularitySwarm

pytestmark = pytest.mark.perf


def test_routing_is_fast(router):
    """Výběr provideru musí být sub-milisekundový."""
    start = time.monotonic()
    for _ in range(10_000):
        router.get_provider(AgentRole.RESEARCHER)
    elapsed = time.monotonic() - start
    assert elapsed < 1.0  # 10k routingů pod 1s


@pytest.mark.asyncio
async def test_orchestrate_runs_in_parallel(router):
    """Paralelní orchestrace nesmí být výrazně pomalejší než jeden agent."""
    swarm = SingularitySwarm(router)
    start = time.monotonic()
    await swarm.orchestrate(
        "úkol", roles=[AgentRole.RESEARCHER, AgentRole.PLANNER, AgentRole.CRITIC]
    )
    elapsed = time.monotonic() - start
    # Mock provideři jsou okamžití; paralelní běh pod 0.5s
    assert elapsed < 0.5


@pytest.mark.asyncio
async def test_concurrent_tasks(router):
    swarm = SingularitySwarm(router)
    results = await asyncio.gather(
        *[swarm.run_agent(AgentRole.RESEARCHER, f"úkol {i}") for i in range(20)]
    )
    assert len(results) == 20
