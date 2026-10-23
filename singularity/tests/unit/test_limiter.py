"""Unit testy ProviderRateLimiter."""
from __future__ import annotations

import pytest

from core.limiter import ProviderRateLimiter

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_acquire_yields_without_config():
    limiter = ProviderRateLimiter()
    async with limiter.acquire("claude"):
        pass  # nemělo by blokovat


@pytest.mark.asyncio
async def test_acquire_with_rpm_config():
    limiter = ProviderRateLimiter(rpm={"claude": 100})
    async with limiter.acquire("claude"):
        pass


def test_has_capacity_unknown_provider_true():
    limiter = ProviderRateLimiter(rpm={"claude": 100})
    assert limiter.has_capacity("unknown") is True
