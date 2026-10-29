"""
Integrační testy — SingularityCore end-to-end s mock providery.

Běží offline: graf je sestaven s mock routerem místo reálných API.
Pro test s reálnými klíči nastav ANTHROPIC_API_KEY a odstraň monkeypatch.
"""
from __future__ import annotations

import pytest

from agents.swarm import SingularitySwarm
from core.graph import SingularityCore
from core.router import LLMRouter

pytestmark = pytest.mark.integration


@pytest.fixture
def core_with_mocks(claude_mock, gemini_mock, monkeypatch):
    """Sestaví SingularityCore, ale s mock routerem/swarmem (bez API klíčů)."""
    router = LLMRouter(claude=claude_mock, gemini=gemini_mock, strategy="static")

    # Obejdi __init__ reálných providerů — nahraď build_router
    monkeypatch.setattr("core.graph.build_router", lambda strategy=None: router)
    core = SingularityCore(router=router)
    core.swarm = SingularitySwarm(router)
    return core


@pytest.mark.asyncio
async def test_full_cognitive_loop(core_with_mocks):
    result = await core_with_mocks.run(
        task="Vysvětli rekurzi",
        user_id="test_user",
        session_id="test-session-1234",
    )
    assert result["response"]
    assert "provider_log" in result
    # Plánovač + kritik + komunikátor proběhli
    assert "plan" in result["provider_log"]
    assert "critique" in result["provider_log"]
    assert "synthesize" in result["provider_log"]


@pytest.mark.asyncio
async def test_provider_log_records_models(core_with_mocks):
    result = await core_with_mocks.run(
        task="úkol",
        user_id="u1",
        session_id="s-abcd1234",
    )
    plog = result["provider_log"]
    # static: plan(PLANNER)→gemini, critique(CRITIC)→claude
    assert plog["plan"] == "gemini"
    assert plog["critique"] == "claude"


@pytest.mark.asyncio
async def test_low_risk_completes_without_approval(core_with_mocks):
    result = await core_with_mocks.run(task="bezpečný úkol", user_id="u", session_id="s-1")
    assert "E-STOP" not in result["response"]
    assert result["risk_score"] < 0.7
