"""Unit testy — HealthMonitor (Fáze 2)."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.health_monitor import HealthMonitor


def _make_monitor(healthy: bool = True, raises: bool = False) -> tuple[HealthMonitor, MagicMock]:
    provider = MagicMock()
    provider.name = "test_provider"
    provider.is_available.return_value = True
    if raises:
        provider.health_check = AsyncMock(side_effect=ConnectionError("down"))
    else:
        provider.health_check = AsyncMock(return_value=healthy)
    provider.record_success = MagicMock()

    router = MagicMock()
    router.all_providers.return_value = [provider]
    return HealthMonitor(router, interval_s=999), provider


@pytest.mark.unit
async def test_run_once_healthy_provider():
    monitor, provider = _make_monitor(healthy=True)
    results = await monitor.run_once()
    assert results["test_provider"] is True
    provider.health_check.assert_called_once()


@pytest.mark.unit
async def test_run_once_unhealthy_provider():
    monitor, provider = _make_monitor(healthy=False)
    results = await monitor.run_once()
    assert results["test_provider"] is False


@pytest.mark.unit
async def test_run_once_exception_returns_false():
    monitor, provider = _make_monitor(raises=True)
    results = await monitor.run_once()
    assert results["test_provider"] is False


@pytest.mark.unit
async def test_run_once_recovers_cooldown_provider():
    """Provider v cooldownu, ale health_check vrací True → record_success()."""
    monitor, provider = _make_monitor(healthy=True)
    provider.is_available.return_value = False   # simuluj cooldown
    await monitor.run_once()
    provider.record_success.assert_called_once()


@pytest.mark.unit
def test_start_stop_does_not_raise():
    import asyncio

    monitor, _ = _make_monitor()

    async def _run():
        monitor.start()
        monitor.stop()

    asyncio.run(_run())
