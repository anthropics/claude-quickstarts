"""
Singularity — Request Coalescer (Fáze 66, v2.0 #6).

Single-flight de-duplication of concurrent identical work. When many callers
request the same thing at once (same cache key), only the first actually runs
the underlying coroutine; the rest await the same in-flight result. This cuts
duplicate LLM calls under bursty load and pairs with the response/semantic
caches (which handle *sequential* repeats) by handling *concurrent* repeats.

Async-only, dependency-free; the key is caller-supplied (e.g. a hash of the
prompt + params).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from typing import Any, Awaitable, Callable


def make_key(*parts: Any) -> str:
    """Stable hash key from arbitrary JSON-able parts."""
    raw = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


class SingleFlight:
    """
    Coalesce concurrent calls sharing a key onto a single execution.

    Usage:
        sf = SingleFlight()
        result = await sf.do(key, lambda: expensive_coro())
    """

    def __init__(self) -> None:
        self._inflight: dict[str, asyncio.Future] = {}
        self._lock = threading.Lock()

        # metrics
        self._calls = 0
        self._executions = 0     # underlying coro actually run
        self._coalesced = 0      # calls served from an in-flight future

    async def do(self, key: str, fn: Callable[[], Awaitable[Any]]) -> Any:
        loop = asyncio.get_event_loop()
        with self._lock:
            self._calls += 1
            fut = self._inflight.get(key)
            if fut is not None:
                self._coalesced += 1
                leader = False
            else:
                fut = loop.create_future()
                self._inflight[key] = fut
                self._executions += 1
                leader = True

        if not leader:
            return await fut

        # leader runs the work and shares the outcome
        try:
            result = await fn()
        except Exception as exc:
            with self._lock:
                self._inflight.pop(key, None)
            if not fut.done():
                fut.set_exception(exc)
                # mark retrieved so a leader with no waiters doesn't trigger
                # asyncio's "Future exception was never retrieved" warning;
                # waiters still receive it via their own `await fut`.
                fut.exception()
            raise
        else:
            with self._lock:
                self._inflight.pop(key, None)
            if not fut.done():
                fut.set_result(result)
            return result

    @property
    def inflight(self) -> int:
        with self._lock:
            return len(self._inflight)

    def metrics(self) -> dict:
        with self._lock:
            calls = self._calls
            return {
                "calls": calls,
                "executions": self._executions,
                "coalesced": self._coalesced,
                "coalesce_rate": round(self._coalesced / calls, 4) if calls else 0.0,
                "inflight": len(self._inflight),
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._calls = 0
            self._executions = 0
            self._coalesced = 0
