"""Unit testy LLMRouter — všech 6 strategií, self-healing, degradace bez Gemini."""
from __future__ import annotations

import pytest

from agents.base import AgentRole
from core.router import LLMRouter

pytestmark = pytest.mark.unit


def test_static_routing_assigns_expected_providers(router):
    assert router.get_provider(AgentRole.RESEARCHER).name == "claude"
    assert router.get_provider(AgentRole.PROGRAMMER).name == "gemini"
    assert router.get_provider(AgentRole.CRITIC).name == "claude"
    assert router.get_provider(AgentRole.PLANNER).name == "gemini"
    assert router.get_provider(AgentRole.COMMUNICATOR).name == "claude"


def test_no_gemini_degrades_to_claude(router_no_gemini):
    assert router_no_gemini.gemini_enabled is False
    for role in AgentRole:
        assert router_no_gemini.get_provider(role).name == "claude"


def test_cost_optimized_picks_cheapest(router):
    router.set_strategy("cost_optimized")
    assert router.get_provider(AgentRole.RESEARCHER).name == "gemini"  # levnější


def test_latency_optimized_picks_fastest(router):
    router.set_strategy("latency_optimized")
    assert router.get_provider(AgentRole.RESEARCHER).name == "gemini"  # nižší latence


def test_quality_first_picks_highest_rank(router):
    router.set_strategy("quality_first")
    assert router.get_provider(AgentRole.PROGRAMMER).name == "claude"  # quality_rank=1


def test_round_robin_alternates(router):
    router.set_strategy("round_robin")
    names = {router.get_provider(AgentRole.RESEARCHER).name for _ in range(4)}
    assert names == {"claude", "gemini"}


def test_failover_returns_other_provider(router, claude_mock):
    fallback = router.get_fallback(claude_mock)
    assert fallback is not None
    assert fallback.name == "gemini"


def test_invalid_strategy_raises(router):
    with pytest.raises(ValueError):
        router.set_strategy("nonsense")


def test_self_healing_cooldown_excludes_provider(claude_mock, gemini_mock):
    router = LLMRouter(claude=claude_mock, gemini=gemini_mock, strategy="static")
    # Vynuť cooldown na gemini
    for _ in range(gemini_mock.COOLDOWN_THRESHOLD):
        gemini_mock.record_failure()
    assert gemini_mock.is_available() is False
    # PROGRAMMER normálně → gemini, ale ten je v cooldownu → claude
    assert router.get_provider(AgentRole.PROGRAMMER).name == "claude"
    assert gemini_mock not in router.available_providers()


def test_record_success_resets_failures(gemini_mock):
    gemini_mock.record_failure()
    gemini_mock.record_failure()
    gemini_mock.record_success()
    assert gemini_mock.consecutive_failures == 0
    assert gemini_mock.is_available() is True
