"""
Unit tests — Health Aggregator (Fáze 57). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.health_aggregator import (
    ComponentHealth,
    HealthAggregator,
    HealthReport,
    HealthStatus,
    _coerce_status,
    _max_status,
)


# ── _coerce_status ───────────────────────────────────────────────────────────────

def test_coerce_status_enum():
    assert _coerce_status(HealthStatus.DEGRADED) == (HealthStatus.DEGRADED, "")


def test_coerce_status_bool_true():
    assert _coerce_status(True)[0] == HealthStatus.HEALTHY


def test_coerce_status_bool_false():
    assert _coerce_status(False)[0] == HealthStatus.UNHEALTHY


def test_coerce_status_string():
    assert _coerce_status("healthy")[0] == HealthStatus.HEALTHY


def test_coerce_status_unknown_string():
    assert _coerce_status("weird")[0] == HealthStatus.UNHEALTHY


def test_coerce_status_tuple():
    s, d = _coerce_status((HealthStatus.DEGRADED, "slow"))
    assert s == HealthStatus.DEGRADED
    assert d == "slow"


def test_coerce_status_garbage():
    assert _coerce_status(object())[0] == HealthStatus.UNHEALTHY


# ── _max_status ──────────────────────────────────────────────────────────────────

def test_max_status_precedence():
    assert _max_status(HealthStatus.HEALTHY, HealthStatus.DEGRADED) == HealthStatus.DEGRADED
    assert _max_status(HealthStatus.DEGRADED, HealthStatus.UNHEALTHY) == HealthStatus.UNHEALTHY
    assert _max_status(HealthStatus.HEALTHY, HealthStatus.HEALTHY) == HealthStatus.HEALTHY


# ── Registration ─────────────────────────────────────────────────────────────────

def test_register_and_list():
    h = HealthAggregator()
    h.register("db", lambda: True)
    h.register("cache", lambda: True)
    assert h.list_components() == ["cache", "db"]


def test_register_requires_name():
    h = HealthAggregator()
    with pytest.raises(ValueError):
        h.register("", lambda: True)


def test_register_requires_callable():
    h = HealthAggregator()
    with pytest.raises(ValueError):
        h.register("x", "not callable")


def test_unregister():
    h = HealthAggregator()
    h.register("db", lambda: True)
    assert h.unregister("db") is True
    assert h.list_components() == []


def test_unregister_missing():
    h = HealthAggregator()
    assert h.unregister("nope") is False


# ── Aggregation ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_all_healthy():
    h = HealthAggregator()
    h.register("a", lambda: True)
    h.register("b", lambda: HealthStatus.HEALTHY)
    report = await h.check()
    assert report.status == HealthStatus.HEALTHY
    assert report.ok is True
    assert report.healthy_count == 2


@pytest.mark.asyncio
async def test_required_unhealthy_makes_overall_unhealthy():
    h = HealthAggregator()
    h.register("db", lambda: False, required=True)
    h.register("cache", lambda: True)
    report = await h.check()
    assert report.status == HealthStatus.UNHEALTHY
    assert report.ok is False


@pytest.mark.asyncio
async def test_optional_unhealthy_makes_overall_degraded():
    h = HealthAggregator()
    h.register("db", lambda: True, required=True)
    h.register("analytics", lambda: False, required=False)
    report = await h.check()
    assert report.status == HealthStatus.DEGRADED
    assert report.ok is True  # degraded still serves


@pytest.mark.asyncio
async def test_degraded_component_degrades_overall():
    h = HealthAggregator()
    h.register("a", lambda: True)
    h.register("b", lambda: HealthStatus.DEGRADED)
    report = await h.check()
    assert report.status == HealthStatus.DEGRADED
    assert report.degraded_count == 1


@pytest.mark.asyncio
async def test_exception_is_unhealthy():
    h = HealthAggregator()
    def _boom():
        raise RuntimeError("db down")
    h.register("db", _boom, required=True)
    report = await h.check()
    assert report.status == HealthStatus.UNHEALTHY
    comp = report.components[0]
    assert "db down" in comp.detail


@pytest.mark.asyncio
async def test_async_check_supported():
    h = HealthAggregator()
    async def _async_check():
        return HealthStatus.HEALTHY
    h.register("svc", _async_check)
    report = await h.check()
    assert report.status == HealthStatus.HEALTHY


@pytest.mark.asyncio
async def test_detail_from_tuple():
    h = HealthAggregator()
    h.register("q", lambda: (HealthStatus.DEGRADED, "lag 5s"))
    report = await h.check()
    assert report.components[0].detail == "lag 5s"


@pytest.mark.asyncio
async def test_empty_aggregator_healthy():
    h = HealthAggregator()
    report = await h.check()
    assert report.status == HealthStatus.HEALTHY
    assert report.components == []


@pytest.mark.asyncio
async def test_latency_recorded():
    h = HealthAggregator()
    h.register("a", lambda: True)
    report = await h.check()
    assert report.components[0].latency_ms >= 0


# ── Worst-case wins ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unhealthy_required_beats_degraded():
    h = HealthAggregator()
    h.register("a", lambda: HealthStatus.DEGRADED)
    h.register("b", lambda: False, required=True)
    report = await h.check()
    assert report.status == HealthStatus.UNHEALTHY


# ── Result shape ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_report_to_dict_shape():
    h = HealthAggregator()
    h.register("a", lambda: True)
    d = (await h.check()).to_dict()
    for key in ("status", "ok", "components", "healthy_count",
                "degraded_count", "unhealthy_count"):
        assert key in d
    for key in ("name", "status", "required", "detail", "latency_ms"):
        assert key in d["components"][0]


# ── Metrics ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_metrics_accumulate():
    h = HealthAggregator()
    h.register("a", lambda: True)
    await h.check()
    h.register("b", lambda: False, required=True)
    await h.check()
    m = h.metrics()
    assert m["total_checks"] == 2
    assert m["unhealthy_reports"] == 1
    assert m["healthy_reports"] == 1


@pytest.mark.asyncio
async def test_metrics_degraded_counted():
    h = HealthAggregator()
    h.register("a", lambda: HealthStatus.DEGRADED)
    await h.check()
    assert h.metrics()["degraded_reports"] == 1


@pytest.mark.asyncio
async def test_metrics_reset():
    h = HealthAggregator()
    h.register("a", lambda: True)
    await h.check()
    h.reset_metrics()
    m = h.metrics()
    assert m["total_checks"] == 0


def test_metrics_shape():
    h = HealthAggregator()
    m = h.metrics()
    for key in ("components", "total_checks", "unhealthy_reports",
                "degraded_reports", "healthy_reports"):
        assert key in m
