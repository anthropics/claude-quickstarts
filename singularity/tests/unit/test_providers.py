"""Unit testy provider abstrakce a self-healing stavu."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_mock_provider_returns_response(claude_mock):
    resp = await claude_mock.ainvoke([])
    assert resp.provider == "claude"
    assert resp.tokens_used == 42
    assert "claude" in resp.content


@pytest.mark.asyncio
async def test_failing_provider_raises(gemini_mock):
    gemini_mock._fail = True
    with pytest.raises(ConnectionError):
        await gemini_mock.ainvoke([])


def test_cooldown_triggers_after_threshold(claude_mock):
    triggered = False
    for _ in range(claude_mock.COOLDOWN_THRESHOLD):
        triggered = claude_mock.record_failure()
    assert triggered is True
    assert claude_mock.is_available() is False


def test_status_snapshot_has_expected_keys(claude_mock):
    status = claude_mock.status()
    for key in ("name", "cost_per_1k", "available", "consecutive_failures"):
        assert key in status


@pytest.mark.asyncio
async def test_health_check_reflects_fail_flag(gemini_mock):
    assert await gemini_mock.health_check() is True
    gemini_mock._fail = True
    assert await gemini_mock.health_check() is False
