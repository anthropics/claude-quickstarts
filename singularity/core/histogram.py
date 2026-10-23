"""
Singularity — Percentile Tracker (Fáze 54).

Streaming latency / value statistics with percentile queries (p50, p90, p95,
p99, …) plus count/min/max/mean over a bounded rolling window per metric.
For SLO monitoring ("is p99 latency under budget?") it complements the
Anomaly Detector (Fáze 52, point outliers) with distribution summaries.

Percentiles use linear-interpolation (type 7) over the retained window.
Dependency-free and deterministic.
"""

from __future__ import annotations

import math
import threading
from collections import deque
from dataclasses import dataclass, field


# ── Result ──────────────────────────────────────────────────────────────────────

@dataclass
class DistributionSummary:
    metric: str
    count: int
    min: float
    max: float
    mean: float
    percentiles: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "count": self.count,
            "min": self.min,
            "max": self.max,
            "mean": self.mean,
            "percentiles": self.percentiles,
        }


def _percentile(sorted_xs: list[float], q: float) -> float:
    """Linear-interpolation percentile (type 7); q in [0, 100]."""
    if not sorted_xs:
        return 0.0
    if len(sorted_xs) == 1:
        return sorted_xs[0]
    pos = (q / 100.0) * (len(sorted_xs) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_xs[lo]
    frac = pos - lo
    return sorted_xs[lo] * (1 - frac) + sorted_xs[hi] * frac


# ── Tracker ─────────────────────────────────────────────────────────────────────

_DEFAULT_PCTS = (50.0, 90.0, 95.0, 99.0)


class PercentileTracker:
    """
    Per-metric bounded-window value tracker with percentile summaries.

    ``window`` caps retained samples per metric; ``percentiles`` is the set of
    quantiles reported by ``summary`` (overridable per call).
    """

    def __init__(
        self,
        *,
        window: int = 1000,
        percentiles: tuple[float, ...] = _DEFAULT_PCTS,
    ) -> None:
        if window < 1:
            raise ValueError("window must be >= 1")
        for p in percentiles:
            if not 0.0 <= p <= 100.0:
                raise ValueError("percentiles must be in [0, 100]")
        self.window = window
        self.percentiles = tuple(percentiles)
        self._streams: dict[str, deque] = {}
        self._lock = threading.Lock()

        # metrics
        self._total_observations = 0

    # ── Recording ───────────────────────────────────────────────────────────────

    def observe(self, metric: str, value: float) -> None:
        with self._lock:
            stream = self._streams.get(metric)
            if stream is None:
                stream = deque(maxlen=self.window)
                self._streams[metric] = stream
            stream.append(float(value))
            self._total_observations += 1

    def observe_many(self, metric: str, values: list[float]) -> None:
        for v in values:
            self.observe(metric, v)

    # ── Queries ───────────────────────────────────────────────────────────────────

    def percentile(self, metric: str, q: float) -> float | None:
        if not 0.0 <= q <= 100.0:
            raise ValueError("q must be in [0, 100]")
        with self._lock:
            stream = self._streams.get(metric)
            if not stream:
                return None
            return round(_percentile(sorted(stream), q), 6)

    def summary(
        self, metric: str, percentiles: tuple[float, ...] | None = None
    ) -> DistributionSummary | None:
        pcts = percentiles or self.percentiles
        with self._lock:
            stream = self._streams.get(metric)
            if not stream:
                return None
            xs = list(stream)
        s = sorted(xs)
        pct_map = {f"p{_fmt(p)}": round(_percentile(s, p), 6) for p in pcts}
        return DistributionSummary(
            metric=metric,
            count=len(xs),
            min=round(s[0], 6),
            max=round(s[-1], 6),
            mean=round(sum(xs) / len(xs), 6),
            percentiles=pct_map,
        )

    # ── Management ──────────────────────────────────────────────────────────────

    def reset_metric(self, metric: str) -> bool:
        with self._lock:
            return self._streams.pop(metric, None) is not None

    def list_metrics(self) -> list[str]:
        with self._lock:
            return sorted(self._streams)

    def metrics(self) -> dict:
        with self._lock:
            return {
                "total_observations": self._total_observations,
                "tracked_metrics": len(self._streams),
                "window": self.window,
                "percentiles": list(self.percentiles),
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total_observations = 0


def _fmt(p: float) -> str:
    """Format a percentile for a key: 99.0 → '99', 99.9 → '99.9'."""
    return str(int(p)) if float(p).is_integer() else str(p)
