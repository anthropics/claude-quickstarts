"""
Singularity — Anomaly Detector (Fáze 52).

Statistical outlier detection on numeric metric streams (latency, cost,
error counts, token usage, …). Maintains a bounded rolling window per metric
and flags new values as anomalies using either:

  - Z_SCORE:  |value − mean| / stdev  >  threshold
  - IQR:      value < Q1 − k·IQR  or  value > Q3 + k·IQR

Complements the threshold-based AlertManager: anomalies are detected
relative to recent behavior, no fixed limit needed. Dependency-free
(pure-Python statistics) and deterministic.
"""

from __future__ import annotations

import math
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum


class DetectionMethod(str, Enum):
    Z_SCORE = "z_score"
    IQR = "iqr"


# ── Result ──────────────────────────────────────────────────────────────────────

@dataclass
class AnomalyResult:
    metric: str
    value: float
    is_anomaly: bool
    method: str
    score: float = 0.0          # z-score, or signed IQR distance in IQR units
    direction: str = "none"     # "high" | "low" | "none"
    window_size: int = 0
    warming_up: bool = False    # not enough history yet

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "value": self.value,
            "is_anomaly": self.is_anomaly,
            "method": self.method,
            "score": self.score,
            "direction": self.direction,
            "window_size": self.window_size,
            "warming_up": self.warming_up,
        }


# ── Statistics helpers ──────────────────────────────────────────────────────────

def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _stdev(xs: list[float], mean: float) -> float:
    if len(xs) < 2:
        return 0.0
    var = sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(var)


def _quantile(sorted_xs: list[float], q: float) -> float:
    """Linear-interpolation quantile (type 7), q in [0,1]."""
    if not sorted_xs:
        return 0.0
    if len(sorted_xs) == 1:
        return sorted_xs[0]
    pos = q * (len(sorted_xs) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_xs[lo]
    frac = pos - lo
    return sorted_xs[lo] * (1 - frac) + sorted_xs[hi] * frac


# ── Detector ────────────────────────────────────────────────────────────────────

class AnomalyDetector:
    """
    Per-metric rolling-window anomaly detection.

    ``window`` caps how many recent observations are retained per metric.
    ``min_samples`` is the warm-up count below which nothing is flagged.
    ``z_threshold`` / ``iqr_k`` tune sensitivity.
    """

    def __init__(
        self,
        *,
        method: DetectionMethod = DetectionMethod.Z_SCORE,
        window: int = 50,
        min_samples: int = 5,
        z_threshold: float = 3.0,
        iqr_k: float = 1.5,
    ) -> None:
        if window < 2:
            raise ValueError("window must be >= 2")
        if min_samples < 2:
            raise ValueError("min_samples must be >= 2")
        if z_threshold <= 0:
            raise ValueError("z_threshold must be > 0")
        if iqr_k <= 0:
            raise ValueError("iqr_k must be > 0")
        self.method = method
        self.window = window
        self.min_samples = min_samples
        self.z_threshold = z_threshold
        self.iqr_k = iqr_k
        self._lock = threading.Lock()

        self._streams: dict[str, deque] = {}

        # metrics
        self._total = 0
        self._anomalies = 0

    # ── Core ──────────────────────────────────────────────────────────────────────

    def observe(
        self,
        metric: str,
        value: float,
        *,
        method: DetectionMethod | None = None,
    ) -> AnomalyResult:
        """Record a value and report whether it is anomalous vs. recent history."""
        m = method or self.method
        with self._lock:
            stream = self._streams.get(metric)
            if stream is None:
                stream = deque(maxlen=self.window)
                self._streams[metric] = stream
            history = list(stream)  # evaluate against history BEFORE adding
            stream.append(float(value))

            self._total += 1
            result = self._evaluate(metric, float(value), history, m)
            if result.is_anomaly:
                self._anomalies += 1
            return result

    def _evaluate(
        self, metric: str, value: float, history: list[float], method: DetectionMethod
    ) -> AnomalyResult:
        n = len(history)
        if n < self.min_samples:
            return AnomalyResult(
                metric=metric, value=value, is_anomaly=False,
                method=method.value, window_size=n, warming_up=True,
            )

        if method == DetectionMethod.IQR:
            return self._iqr(metric, value, history)
        return self._zscore(metric, value, history)

    def _zscore(self, metric: str, value: float, history: list[float]) -> AnomalyResult:
        mean = _mean(history)
        sd = _stdev(history, mean)
        if sd == 0.0:
            # flat history → anomaly iff value differs at all
            is_anom = value != mean
            return AnomalyResult(
                metric=metric, value=value, is_anomaly=is_anom,
                method="z_score", score=0.0,
                direction=("high" if value > mean else "low") if is_anom else "none",
                window_size=len(history),
            )
        z = (value - mean) / sd
        is_anom = abs(z) > self.z_threshold
        return AnomalyResult(
            metric=metric, value=value, is_anomaly=is_anom, method="z_score",
            score=round(z, 6),
            direction="high" if z > 0 else "low" if z < 0 else "none",
            window_size=len(history),
        )

    def _iqr(self, metric: str, value: float, history: list[float]) -> AnomalyResult:
        s = sorted(history)
        q1 = _quantile(s, 0.25)
        q3 = _quantile(s, 0.75)
        iqr = q3 - q1
        lower = q1 - self.iqr_k * iqr
        upper = q3 + self.iqr_k * iqr
        if value > upper:
            direction, is_anom = "high", True
        elif value < lower:
            direction, is_anom = "low", True
        else:
            direction, is_anom = "none", False
        # signed distance in IQR units (0 if iqr == 0 handled)
        if iqr > 0:
            if value > upper:
                score = round((value - q3) / iqr, 6)
            elif value < lower:
                score = round((value - q1) / iqr, 6)
            else:
                score = 0.0
        else:
            is_anom = value != q1
            direction = ("high" if value > q1 else "low") if is_anom else "none"
            score = 0.0
        return AnomalyResult(
            metric=metric, value=value, is_anomaly=is_anom, method="iqr",
            score=score, direction=direction, window_size=len(history),
        )

    # ── Management ──────────────────────────────────────────────────────────────

    def reset_stream(self, metric: str) -> bool:
        with self._lock:
            return self._streams.pop(metric, None) is not None

    def stream_size(self, metric: str) -> int:
        with self._lock:
            return len(self._streams.get(metric, ()))

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def metrics(self) -> dict:
        with self._lock:
            n = self._total
            return {
                "total_observations": n,
                "anomalies": self._anomalies,
                "anomaly_rate": round(self._anomalies / n, 4) if n else 0.0,
                "tracked_metrics": len(self._streams),
                "method": self.method.value,
                "window": self.window,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total = 0
            self._anomalies = 0
