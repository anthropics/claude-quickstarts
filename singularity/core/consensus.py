"""
Singularity — Self-Consistency Consensus Engine (Fáze 33).

Samples the same prompt multiple times, clusters the candidate answers by
normalized similarity, and returns the majority cluster's answer together
with a confidence score (cluster size / total samples).

This implements the "self-consistency" decoding idea: instead of trusting a
single sample, draw several and let agreement decide. Provider-agnostic via
an injectable async ``sample_fn`` so it is fully testable offline.
"""

from __future__ import annotations

import asyncio
import re
import threading
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Awaitable, Callable


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace — for grouping."""
    text = (text or "").lower()
    text = re.sub(r"[^\w\s]", "", text)
    return " ".join(text.split())


def _similar(a: str, b: str) -> float:
    """Ratio in [0,1] between two normalized strings."""
    if not a and not b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


# ── Result ──────────────────────────────────────────────────────────────────────

@dataclass
class ConsensusResult:
    answer: str
    confidence: float                 # majority cluster size / total samples
    sample_count: int
    cluster_count: int
    clusters: list[dict] = field(default_factory=list)  # [{answer, size, members}]
    agreement: bool = False           # True if confidence >= threshold
    samples: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "confidence": self.confidence,
            "sample_count": self.sample_count,
            "cluster_count": self.cluster_count,
            "clusters": self.clusters,
            "agreement": self.agreement,
            "samples": self.samples,
        }


# ── Engine ──────────────────────────────────────────────────────────────────────

SampleFn = Callable[[list[dict]], Awaitable[str]]


class ConsensusEngine:
    """
    Draw ``n_samples`` responses and pick the majority answer.

    Clustering: two answers join the same cluster if their normalized
    similarity >= ``similarity_threshold`` (default 0.9). With threshold 1.0
    this degenerates to exact normalized-string grouping.

    ``agreement_threshold`` decides whether the result counts as a confident
    consensus (confidence >= threshold).
    """

    def __init__(
        self,
        *,
        n_samples: int = 5,
        similarity_threshold: float = 0.9,
        agreement_threshold: float = 0.5,
    ) -> None:
        if n_samples < 1:
            raise ValueError("n_samples must be >= 1")
        if not 0.0 < similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold must be in (0.0, 1.0]")
        if not 0.0 < agreement_threshold <= 1.0:
            raise ValueError("agreement_threshold must be in (0.0, 1.0]")
        self.n_samples = n_samples
        self.similarity_threshold = similarity_threshold
        self.agreement_threshold = agreement_threshold
        self._lock = threading.Lock()

        # metrics
        self._total_runs = 0
        self._agreements = 0
        self._total_confidence = 0.0

    # ── Public API ──────────────────────────────────────────────────────────────

    async def run(
        self,
        messages: list[dict],
        sample_fn: SampleFn,
        *,
        n_samples: int | None = None,
    ) -> ConsensusResult:
        n = self.n_samples if n_samples is None else n_samples
        if n < 1:
            raise ValueError("n_samples must be >= 1")

        # Draw samples concurrently.
        samples = await asyncio.gather(*[sample_fn(messages) for _ in range(n)])
        return self._consensus_from_samples(list(samples))

    def from_samples(self, samples: list[str]) -> ConsensusResult:
        """Compute consensus over already-collected samples (sync, no LLM)."""
        return self._consensus_from_samples(list(samples))

    # ── Core clustering ──────────────────────────────────────────────────────────

    def _consensus_from_samples(self, samples: list[str]) -> ConsensusResult:
        if not samples:
            self._record(0.0, agreement=False)
            return ConsensusResult(
                answer="", confidence=0.0, sample_count=0,
                cluster_count=0, clusters=[], agreement=False, samples=[],
            )

        clusters = self._cluster(samples)
        # Sort clusters by size (desc), tie-break by first appearance order.
        clusters.sort(key=lambda c: (-len(c["members"]), c["first_index"]))

        top = clusters[0]
        confidence = len(top["members"]) / len(samples)
        agreement = confidence >= self.agreement_threshold

        cluster_dicts = [
            {
                "answer": c["representative"],
                "size": len(c["members"]),
                "members": c["members"],
            }
            for c in clusters
        ]

        self._record(confidence, agreement=agreement)
        return ConsensusResult(
            answer=top["representative"],
            confidence=round(confidence, 4),
            sample_count=len(samples),
            cluster_count=len(clusters),
            clusters=cluster_dicts,
            agreement=agreement,
            samples=samples,
        )

    def _cluster(self, samples: list[str]) -> list[dict]:
        """
        Greedy single-pass clustering. Each sample joins the first existing
        cluster whose representative is similar enough; otherwise starts a new
        cluster. The representative is the first member (stable).
        """
        clusters: list[dict] = []
        norms = [_normalize(s) for s in samples]

        for idx, (raw, norm) in enumerate(zip(samples, norms)):
            placed = False
            for c in clusters:
                if self.similarity_threshold >= 1.0:
                    match = norm == c["norm"]
                else:
                    match = _similar(norm, c["norm"]) >= self.similarity_threshold
                if match:
                    c["members"].append(idx)
                    placed = True
                    break
            if not placed:
                clusters.append({
                    "representative": raw,
                    "norm": norm,
                    "members": [idx],
                    "first_index": idx,
                })
        return clusters

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def _record(self, confidence: float, *, agreement: bool) -> None:
        with self._lock:
            self._total_runs += 1
            self._total_confidence += confidence
            if agreement:
                self._agreements += 1

    def metrics(self) -> dict:
        with self._lock:
            runs = self._total_runs
            return {
                "total_runs": runs,
                "agreements": self._agreements,
                "agreement_rate": round(self._agreements / runs, 4) if runs else 0.0,
                "avg_confidence": round(self._total_confidence / runs, 4) if runs else 0.0,
                "n_samples": self.n_samples,
                "similarity_threshold": self.similarity_threshold,
                "agreement_threshold": self.agreement_threshold,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total_runs = 0
            self._agreements = 0
            self._total_confidence = 0.0
