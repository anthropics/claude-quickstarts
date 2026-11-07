"""
Unit tests — Request Coalescer (Fáze 66). Fully offline, async.
"""

from __future__ import annotations

import asyncio
import pytest

from core.coalescer import SingleFlight, make_key


# ── make_key ─────────────────────────────────────────────────────────────────────

def test_make_key_deterministic():
    assert make_key("a", 1) == make_key("a", 1)


def test_make_key_differs():
    assert make_key("a", 1) != make_key("a", 2)


def test_make_key_order_independent_for_kwargs_dict():
    # dicts hashed with sorted keys → stable regardless of insertion order
    assert make_key({"x": 1, "y": 2}) == make_key({"y": 2, "x": 1})


# ── Single execution ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_single_call_executes():
    sf = SingleFlight()
    result = await sf.do("k", lambda: _const(42))
    assert result == 42
    m = sf.metrics()
    assert m["executions"] == 1
    assert m["coalesced"] == 0


@pytest.mark.asyncio
async def test_concurrent_identical_coalesced():
    sf = SingleFlight()
    runs = {"n": 0}

    async def _work():
        runs["n"] += 1
        await asyncio.sleep(0.02)  # keep it in-flight so others join
        return "shared"

    results = await asyncio.gather(*[sf.do("same", _work) for _ in range(10)])
    assert results == ["shared"] * 10
    assert runs["n"] == 1               # underlying ran once
    m = sf.metrics()
    assert m["executions"] == 1
    assert m["coalesced"] == 9
    assert m["calls"] == 10


@pytest.mark.asyncio
async def test_different_keys_run_separately():
    sf = SingleFlight()
    runs = {"n": 0}

    async def _work():
        runs["n"] += 1
        await asyncio.sleep(0.01)
        return runs["n"]

    await asyncio.gather(sf.do("a", _work), sf.do("b", _work))
    assert runs["n"] == 2
    assert sf.metrics()["executions"] == 2


@pytest.mark.asyncio
async def test_sequential_calls_not_coalesced():
    sf = SingleFlight()
    await sf.do("k", lambda: _const(1))
    await sf.do("k", lambda: _const(2))  # first already resolved & cleared
    m = sf.metrics()
    assert m["executions"] == 2
    assert m["coalesced"] == 0


# ── Exceptions ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_exception_propagates_to_all_waiters():
    sf = SingleFlight()

    async def _boom():
        await asyncio.sleep(0.01)
        raise ValueError("fail")

    async def _call():
        with pytest.raises(ValueError):
            await sf.do("k", _boom)

    await asyncio.gather(*[_call() for _ in range(5)])
    # key is cleaned up so a later call can retry
    assert sf.inflight == 0


@pytest.mark.asyncio
async def test_key_cleared_after_success():
    sf = SingleFlight()
    await sf.do("k", lambda: _const(1))
    assert sf.inflight == 0


@pytest.mark.asyncio
async def test_retry_after_exception():
    sf = SingleFlight()

    async def _boom():
        raise RuntimeError("x")

    with pytest.raises(RuntimeError):
        await sf.do("k", _boom)
    # subsequent call with same key succeeds (not stuck on failed future)
    result = await sf.do("k", lambda: _const("ok"))
    assert result == "ok"


# ── Metrics ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_metrics_coalesce_rate():
    sf = SingleFlight()

    async def _work():
        await asyncio.sleep(0.02)
        return 1

    await asyncio.gather(*[sf.do("k", _work) for _ in range(4)])
    m = sf.metrics()
    assert m["calls"] == 4
    assert m["coalesce_rate"] == 0.75  # 3 of 4 coalesced


@pytest.mark.asyncio
async def test_metrics_reset():
    sf = SingleFlight()
    await sf.do("k", lambda: _const(1))
    sf.reset_metrics()
    m = sf.metrics()
    assert m["calls"] == 0
    assert m["executions"] == 0


def test_metrics_shape():
    sf = SingleFlight()
    m = sf.metrics()
    for key in ("calls", "executions", "coalesced", "coalesce_rate", "inflight"):
        assert key in m


# ── helper ───────────────────────────────────────────────────────────────────────

async def _const(v):
    return v
