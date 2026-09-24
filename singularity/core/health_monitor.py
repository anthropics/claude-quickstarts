"""
Singularity — Background health monitor (Fáze 2).

Periodicky volá health_check() na všech providerech a aktualizuje jejich
self-healing stav. Reaguje i na obnovu po cooldownu.
"""
from __future__ import annotations

import asyncio

import structlog

from core import telemetry
from core.router import LLMRouter

log = structlog.get_logger()


class HealthMonitor:
    """Asyncio background task: pravidelný health check všech LLM providerů."""

    def __init__(self, router: LLMRouter, interval_s: float = 30.0) -> None:
        self.router = router
        self.interval_s = interval_s
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop(), name="health_monitor")
        log.info("health_monitor_started", interval_s=self.interval_s)

    def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            log.info("health_monitor_stopped")

    async def run_once(self) -> dict[str, bool]:
        """Okamžitý jednorázový check — vhodný pro testy."""
        results: dict[str, bool] = {}
        for provider in self.router.all_providers():
            results[provider.name] = await self._check_provider(provider)
        return results

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.interval_s)
                await self.run_once()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error("health_monitor_loop_error", error=str(exc))

    async def _check_provider(self, provider) -> bool:
        import time

        t0 = time.monotonic()
        try:
            healthy = await provider.health_check()
            latency = time.monotonic() - t0
            status = "ok" if healthy else "unhealthy"
            telemetry.record_request(provider.name, "health_monitor", status, latency)
            if healthy and not provider.is_available():
                # Provider se zotavil z cooldownu — resetuj
                provider.record_success()
                log.info("provider_recovered", provider=provider.name)
            log.debug("health_check_done", provider=provider.name, healthy=healthy)
            return healthy
        except Exception as exc:
            telemetry.record_request(provider.name, "health_monitor", "error", 0.0)
            log.warning("health_check_exception", provider=provider.name, error=str(exc))
            return False
