"""
Singularity — Reservoir Sampler (Fáze 53).

Uniform random sampling over an unbounded stream using Vitter's Algorithm R.
Keeps a fixed-size reservoir so a representative sample of high-volume items
(log lines, requests, traces, eval cases) can be retained in O(k) memory
without knowing the stream length in advance — every item seen has equal
probability k/n of being in the final sample.

Determinism: an injectable seed makes runs reproducible for tests. Also
provides simple Bernoulli (rate-based) sampling. Dependency-free.
"""

from __future__ import annotations

import random
import threading
from dataclasses import dataclass, field
from typing import Any


# ── Result ──────────────────────────────────────────────────────────────────────

@dataclass
class SampleState:
    capacity: int
    seen: int
    sample_size: int
    items: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "capacity": self.capacity,
            "seen": self.seen,
            "sample_size": self.sample_size,
            "items": self.items,
        }


# ── Reservoir ───────────────────────────────────────────────────────────────────

class ReservoirSampler:
    """
    Fixed-capacity uniform reservoir (Algorithm R).

    For the first ``capacity`` items the reservoir fills directly; afterward
    the n-th item (1-indexed) replaces a random reservoir slot with
    probability capacity/n, preserving uniformity.
    """

    def __init__(self, capacity: int, *, seed: int | None = None) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self._rng = random.Random(seed)
        self._reservoir: list[Any] = []
        self._seen = 0
        self._replacements = 0
        self._lock = threading.Lock()

    def add(self, item: Any) -> bool:
        """Offer one item to the reservoir. Returns True if it is currently kept."""
        with self._lock:
            self._seen += 1
            if len(self._reservoir) < self.capacity:
                self._reservoir.append(item)
                return True
            # replace slot j with probability capacity/seen
            j = self._rng.randint(0, self._seen - 1)
            if j < self.capacity:
                self._reservoir[j] = item
                self._replacements += 1
                return True
            return False

    def add_many(self, items: list[Any]) -> int:
        kept = 0
        for it in items:
            if self.add(it):
                kept += 1
        return kept

    def sample(self) -> list[Any]:
        with self._lock:
            return list(self._reservoir)

    def reset(self) -> None:
        with self._lock:
            self._reservoir.clear()
            self._seen = 0
            self._replacements = 0

    @property
    def seen(self) -> int:
        with self._lock:
            return self._seen

    def state(self) -> SampleState:
        with self._lock:
            return SampleState(
                capacity=self.capacity,
                seen=self._seen,
                sample_size=len(self._reservoir),
                items=list(self._reservoir),
            )

    def metrics(self) -> dict:
        with self._lock:
            return {
                "capacity": self.capacity,
                "seen": self._seen,
                "sample_size": len(self._reservoir),
                "replacements": self._replacements,
                "fill_ratio": round(len(self._reservoir) / self.capacity, 4),
            }


# ── Bernoulli (rate) sampler ────────────────────────────────────────────────────

class RateSampler:
    """Keep each item independently with probability ``rate`` (Bernoulli)."""

    def __init__(self, rate: float, *, seed: int | None = None) -> None:
        if not 0.0 <= rate <= 1.0:
            raise ValueError("rate must be in [0.0, 1.0]")
        self.rate = rate
        self._rng = random.Random(seed)
        self._seen = 0
        self._kept = 0
        self._lock = threading.Lock()

    def should_sample(self) -> bool:
        with self._lock:
            self._seen += 1
            if self.rate >= 1.0:
                keep = True
            elif self.rate <= 0.0:
                keep = False
            else:
                keep = self._rng.random() < self.rate
            if keep:
                self._kept += 1
            return keep

    def metrics(self) -> dict:
        with self._lock:
            n = self._seen
            return {
                "rate": self.rate,
                "seen": n,
                "kept": self._kept,
                "effective_rate": round(self._kept / n, 4) if n else 0.0,
            }

    def reset(self) -> None:
        with self._lock:
            self._seen = 0
            self._kept = 0
