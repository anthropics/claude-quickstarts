"""
Singularity — Health Aggregator (Fáze 57).

Composes per-subsystem health checks into a single overall status. Each
component registers a check callable returning healthy/degraded/unhealthy
(or a bool / raising); the aggregator runs them all and rolls them up:

  - any REQUIRED component unhealthy        → overall UNHEALTHY
  - any component degraded, or an OPTIONAL  → overall DEGRADED
    component unhealthy
  - otherwise                               → HEALTHY

This unifies the scattered ``*/metrics`` and ad-hoc probes behind one
readiness view. Check callables are injected, so it is fully offline-testable
and supports both sync and async checks.

Dependency-free.
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


# A check returns a HealthStatus, a bool (True=healthy/False=unhealthy),
# a (status, detail) tuple, or raises (→ unhealthy).
CheckFn = Callable[[], Any]


_RANK = {HealthStatus.HEALTHY: 0, HealthStatus.DEGRADED: 1, HealthStatus.UNHEALTHY: 2}


@dataclass
class ComponentHealth:
    name: str
    status: HealthStatus
    required: bool
    detail: str = ""
    latency_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "required": self.required,
            "detail": self.detail,
            "latency_ms": self.latency_ms,
        }


@dataclass
class HealthReport:
    status: HealthStatus
    components: list[ComponentHealth] = field(default_factory=list)
    healthy_count: int = 0
    degraded_count: int = 0
    unhealthy_count: int = 0

    @property
    def ok(self) -> bool:
        return self.status != HealthStatus.UNHEALTHY

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "ok": self.ok,
            "components": [c.to_dict() for c in self.components],
            "healthy_count": self.healthy_count,
            "degraded_count": self.degraded_count,
            "unhealthy_count": self.unhealthy_count,
        }


def _coerce_status(raw: Any) -> tuple[HealthStatus, str]:
    if isinstance(raw, HealthStatus):
        return raw, ""
    if isinstance(raw, bool):
        return (HealthStatus.HEALTHY if raw else HealthStatus.UNHEALTHY), ""
    if isinstance(raw, str):
        try:
            return HealthStatus(raw), ""
        except ValueError:
            return HealthStatus.UNHEALTHY, f"unknown status: {raw!r}"
    if isinstance(raw, tuple) and len(raw) == 2:
        status, _ = _coerce_status(raw[0])
        return status, str(raw[1])
    return HealthStatus.UNHEALTHY, f"uninterpretable check result: {type(raw).__name__}"


# ── Aggregator ──────────────────────────────────────────────────────────────────

class HealthAggregator:
    """Register component checks, then ``check()`` for a rolled-up report."""

    def __init__(self) -> None:
        self._checks: dict[str, tuple[CheckFn, bool]] = {}  # name -> (fn, required)
        self._lock = threading.Lock()

        # metrics
        self._total_checks = 0
        self._unhealthy_reports = 0
        self._degraded_reports = 0

    # ── Registration ──────────────────────────────────────────────────────────────

    def register(self, name: str, check: CheckFn, *, required: bool = True) -> None:
        if not name:
            raise ValueError("component name is required")
        if not callable(check):
            raise ValueError("check must be callable")
        with self._lock:
            self._checks[name] = (check, required)

    def unregister(self, name: str) -> bool:
        with self._lock:
            return self._checks.pop(name, None) is not None

    def list_components(self) -> list[str]:
        with self._lock:
            return sorted(self._checks)

    # ── Evaluation ────────────────────────────────────────────────────────────────

    async def check(self) -> HealthReport:
        with self._lock:
            items = list(self._checks.items())

        components: list[ComponentHealth] = []
        for name, (fn, required) in items:
            components.append(await self._run_one(name, fn, required))

        report = self._aggregate(components)
        with self._lock:
            self._total_checks += 1
            if report.status == HealthStatus.UNHEALTHY:
                self._unhealthy_reports += 1
            elif report.status == HealthStatus.DEGRADED:
                self._degraded_reports += 1
        return report

    async def _run_one(self, name: str, fn: CheckFn, required: bool) -> ComponentHealth:
        t0 = time.monotonic()
        try:
            result = fn()
            if asyncio.iscoroutine(result):
                result = await result
            status, detail = _coerce_status(result)
        except Exception as exc:
            status, detail = HealthStatus.UNHEALTHY, f"{type(exc).__name__}: {exc}"
        return ComponentHealth(
            name=name, status=status, required=required, detail=detail,
            latency_ms=round((time.monotonic() - t0) * 1000, 3),
        )

    @staticmethod
    def _aggregate(components: list[ComponentHealth]) -> HealthReport:
        healthy = degraded = unhealthy = 0
        overall = HealthStatus.HEALTHY
        for c in components:
            if c.status == HealthStatus.HEALTHY:
                healthy += 1
            elif c.status == HealthStatus.DEGRADED:
                degraded += 1
                overall = _max_status(overall, HealthStatus.DEGRADED)
            else:  # unhealthy
                unhealthy += 1
                if c.required:
                    overall = _max_status(overall, HealthStatus.UNHEALTHY)
                else:
                    overall = _max_status(overall, HealthStatus.DEGRADED)
        return HealthReport(
            status=overall, components=components,
            healthy_count=healthy, degraded_count=degraded, unhealthy_count=unhealthy,
        )

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def metrics(self) -> dict:
        with self._lock:
            n = self._total_checks
            return {
                "components": len(self._checks),
                "total_checks": n,
                "unhealthy_reports": self._unhealthy_reports,
                "degraded_reports": self._degraded_reports,
                "healthy_reports": n - self._unhealthy_reports - self._degraded_reports,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total_checks = 0
            self._unhealthy_reports = 0
            self._degraded_reports = 0


def _max_status(a: HealthStatus, b: HealthStatus) -> HealthStatus:
    return a if _RANK[a] >= _RANK[b] else b
