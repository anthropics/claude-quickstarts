"""
Singularity — Rate limiting per provider.

Token-bucket limiter (aiolimiter) chrání před překročením RPM limitů
jednotlivých LLM API. Pokud aiolimiter není dostupný, degraduje na no-op.
"""
from __future__ import annotations

import contextlib
import structlog

log = structlog.get_logger()

try:
    from aiolimiter import AsyncLimiter

    _LIMITER_AVAILABLE = True
except Exception:  # pragma: no cover - aiolimiter volitelný
    _LIMITER_AVAILABLE = False
    AsyncLimiter = None  # type: ignore[assignment, misc]


class ProviderRateLimiter:
    """
    Spravuje samostatný token bucket pro každého providera.

    Args:
        rpm: dict provider_name → max požadavků za minutu.
    """

    def __init__(self, rpm: dict[str, int] | None = None) -> None:
        self._rpm = rpm or {}
        self._limiters: dict[str, object] = {}

        if _LIMITER_AVAILABLE:
            for name, limit in self._rpm.items():
                # AsyncLimiter(max_rate, time_period) — time_period v sekundách
                self._limiters[name] = AsyncLimiter(limit, 60)
            log.info("rate_limiter_init", providers=list(self._rpm.keys()))
        else:
            log.info("rate_limiter_disabled", reason="aiolimiter not installed")

    @contextlib.asynccontextmanager
    async def acquire(self, provider: str):
        """
        Async context manager — počká na volný slot pro daného providera.
        Použití: `async with limiter.acquire("claude"): ...`
        """
        limiter = self._limiters.get(provider)
        if limiter is not None:
            async with limiter:  # type: ignore[union-attr]
                yield
        else:
            yield

    def has_capacity(self, provider: str) -> bool:
        """True pokud má provider okamžitě volnou kapacitu (bez čekání)."""
        limiter = self._limiters.get(provider)
        if limiter is None:
            return True
        return limiter.has_capacity()  # type: ignore[union-attr]
