"""
Singularity — SLO Monitor (Fáze 58).

Service-Level-Objective tracking — the observability capstone tying together
the metric primitives (Percentile Tracker Fáze 54, Anomaly Detector Fáze 52).
Define SLOs with a target compliance over a rolling window of events, then:

  - SLI:            good events / total events (the achieved level)
  - error budget:   how much failure the target permits, and how much remains
  - burn rate:      observed failure rate ÷ allowed failure rate
                    (>1 = burning budget faster than sustainable)
  - status:         HEALTHY / WARNING (budget < 25 %) / BREACHED (SLI < target)

Two SLO kinds:
  - AVAILABILITY:   record_success() / record_failure()
  - LATENCY:        record_latency(ms); good iff <= threshold_ms

Dependency-free and deterministic.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum


class SLOKind(str, Enum):
    AVAILABILITY = "availability"
    LATENCY = "latency"


class SLOStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"      # budget mostly consumed
    BREACHED = "breached"    # SLI below target


@dataclass
class SLOReport:
    name: str
    kind: str
    target: float            # e.g. 0.999
    window: int
    total: int
    good: int
    bad: int
    sli: float               # achieved compliance [0,1]
    error_budget: float      # allowed failure fraction = 1 - target
    budget_remaining: float  # [0,1] fraction of error budget left (clamped)
    burn_rate: float         # observed_fail_rate / allowed_fail_rate
    status: str

    def to_dict(self) -> dict:
        return {
            "name": self.name, "kind": self.kind, "target": self.target,
            "window": self.window, "total": self.total, "good": self.good,
            "bad": self.bad, "sli": self.sli, "error_budget": self.error_budget,
            "budget_remaining": self.budget_remaining, "burn_rate": self.burn_rate,
            "status": self.status,
        }


@dataclass
class _SLO:
    name: str
    kind: SLOKind
    target: float
    window: int
    threshold_ms: float | None = None
    events: deque = field(default_factory=deque)  # 1 = good, 0 = bad
    warning_at: float = 0.25  # budget-remaining threshold for WARNING


# ── Monitor ─────────────────────────────────────────────────────────────────────

class SLOMonitor:
    """Register SLOs, record events, and report compliance / budget / burn."""

    def __init__(self) -> None:
        self._slos: dict[str, _SLO] = {}
        self._lock = threading.Lock()
        self._breaches = 0  # cumulative breach observations

    # ── Registration ──────────────────────────────────────────────────────────────

    def register(
        self,
        name: str,
        *,
        kind: SLOKind = SLOKind.AVAILABILITY,
        target: float = 0.99,
        window: int = 1000,
        threshold_ms: float | None = None,
    ) -> None:
        if not name:
            raise ValueError("SLO name is required")
        if not 0.0 < target < 1.0:
            raise ValueError("target must be in (0.0, 1.0)")
        if window < 1:
            raise ValueError("window must be >= 1")
        if kind == SLOKind.LATENCY and threshold_ms is None:
            raise ValueError("latency SLO requires threshold_ms")
        with self._lock:
            self._slos[name] = _SLO(
                name=name, kind=kind, target=target, window=window,
                threshold_ms=threshold_ms, events=deque(maxlen=window),
            )

    def delete(self, name: str) -> bool:
        with self._lock:
            return self._slos.pop(name, None) is not None

    def list_slos(self) -> list[str]:
        with self._lock:
            return sorted(self._slos)

    # ── Recording ─────────────────────────────────────────────────────────────────

    def record_success(self, name: str) -> None:
        self._record(name, 1)

    def record_failure(self, name: str) -> None:
        self._record(name, 0)

    def record_latency(self, name: str, latency_ms: float) -> None:
        with self._lock:
            slo = self._slos.get(name)
            if slo is None:
                raise KeyError(f"Unknown SLO {name!r}")
            if slo.kind != SLOKind.LATENCY:
                raise ValueError(f"SLO {name!r} is not a latency SLO")
            slo.events.append(1 if latency_ms <= slo.threshold_ms else 0)

    def _record(self, name: str, good: int) -> None:
        with self._lock:
            slo = self._slos.get(name)
            if slo is None:
                raise KeyError(f"Unknown SLO {name!r}")
            slo.events.append(good)

    # ── Reporting ─────────────────────────────────────────────────────────────────

    def report(self, name: str) -> SLOReport:
        with self._lock:
            slo = self._slos.get(name)
            if slo is None:
                raise KeyError(f"Unknown SLO {name!r}")
            events = list(slo.events)
            target = slo.target
            warning_at = slo.warning_at
            kind = slo.kind.value
            window = slo.window

        total = len(events)
        good = sum(events)
        bad = total - good
        sli = (good / total) if total else 1.0
        error_budget = round(1.0 - target, 6)
        allowed_fail = 1.0 - target
        observed_fail = (bad / total) if total else 0.0

        # fraction of error budget remaining (1 = none used, 0 = fully spent)
        if allowed_fail <= 0:
            budget_remaining = 1.0
        else:
            budget_remaining = 1.0 - (observed_fail / allowed_fail)
        budget_remaining = round(max(0.0, min(1.0, budget_remaining)), 6)

        burn_rate = round(observed_fail / allowed_fail, 6) if allowed_fail > 0 else 0.0

        if total and sli < target:
            status = SLOStatus.BREACHED
        elif budget_remaining < warning_at:
            status = SLOStatus.WARNING
        else:
            status = SLOStatus.HEALTHY

        if status == SLOStatus.BREACHED:
            with self._lock:
                self._breaches += 1

        return SLOReport(
            name=name, kind=kind, target=target, window=window,
            total=total, good=good, bad=bad, sli=round(sli, 6),
            error_budget=error_budget, budget_remaining=budget_remaining,
            burn_rate=burn_rate, status=status.value,
        )

    def report_all(self) -> list[dict]:
        with self._lock:
            names = list(self._slos)
        return [self.report(n).to_dict() for n in names]

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def metrics(self) -> dict:
        with self._lock:
            return {
                "slos": len(self._slos),
                "breach_observations": self._breaches,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._breaches = 0
