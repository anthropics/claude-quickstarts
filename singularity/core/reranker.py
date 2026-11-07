"""
Singularity — Hybrid Reranker (Fáze 38).

Fuses several ranked result lists (e.g. BM25 lexical retrieval + dense
semantic retrieval) into a single consensus ranking. Two fusion methods:

  - RECIPROCAL_RANK (RRF):  rank-based, score-agnostic. Each list contributes
        1 / (k + rank) per document; robust when source scores are on
        different scales.
  - WEIGHTED_SCORE:  min-max normalizes each list's scores to [0,1], then
        combines with per-list weights. Use when raw scores are comparable
        and you want magnitude to matter.

Pure-Python, deterministic, dependency-free — pairs with the BM25 Retriever
(Fáze 37) and Semantic Cache (Fáze 29) to build hybrid RAG.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum


# ── Method ──────────────────────────────────────────────────────────────────────

class FusionMethod(str, Enum):
    RECIPROCAL_RANK = "reciprocal_rank"
    WEIGHTED_SCORE = "weighted_score"


# ── Data structures ─────────────────────────────────────────────────────────────

@dataclass
class RankedItem:
    doc_id: str
    score: float = 0.0
    text: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class FusedResult:
    doc_id: str
    fused_score: float
    rank: int
    sources: list[str] = field(default_factory=list)   # which lists contributed
    text: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "fused_score": self.fused_score,
            "rank": self.rank,
            "sources": self.sources,
            "text": self.text,
            "metadata": self.metadata,
        }


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _coerce(item) -> RankedItem:
    if isinstance(item, RankedItem):
        return item
    if isinstance(item, dict):
        return RankedItem(
            doc_id=str(item.get("doc_id", item.get("id", ""))),
            score=float(item.get("score", 0.0)),
            text=item.get("text", ""),
            metadata=item.get("metadata", {}) or {},
        )
    # plain string → doc_id only
    return RankedItem(doc_id=str(item))


def _minmax_normalize(scores: list[float]) -> list[float]:
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return [1.0 for _ in scores]   # all equal → all top
    span = hi - lo
    return [(s - lo) / span for s in scores]


# ── Reranker ────────────────────────────────────────────────────────────────────

class HybridReranker:
    """
    Combine multiple ranked lists into one.

    ``rrf_k`` is the RRF damping constant (typical 60). ``default_method``
    selects the fusion method when ``fuse`` is called without an override.
    """

    def __init__(
        self,
        *,
        rrf_k: int = 60,
        default_method: FusionMethod = FusionMethod.RECIPROCAL_RANK,
    ) -> None:
        if rrf_k < 1:
            raise ValueError("rrf_k must be >= 1")
        self.rrf_k = rrf_k
        self.default_method = default_method
        self._lock = threading.Lock()

        # metrics
        self._total_fusions = 0
        self._total_inputs = 0
        self._total_outputs = 0

    # ── Public API ──────────────────────────────────────────────────────────────

    def fuse(
        self,
        ranked_lists: list[list],
        *,
        method: FusionMethod | None = None,
        weights: list[float] | None = None,
        top_k: int | None = None,
    ) -> list[FusedResult]:
        m = method or self.default_method
        lists = [[_coerce(it) for it in lst] for lst in ranked_lists]

        if weights is not None and len(weights) != len(lists):
            raise ValueError("weights length must match number of ranked_lists")
        w = weights or [1.0] * len(lists)

        if m == FusionMethod.WEIGHTED_SCORE:
            fused = self._weighted_score(lists, w)
        else:
            fused = self._reciprocal_rank(lists, w)

        fused.sort(key=lambda r: (-r.fused_score, r.doc_id))
        for i, r in enumerate(fused):
            r.rank = i
        if top_k is not None:
            fused = fused[:top_k]

        self._record(sum(len(lst) for lst in lists), len(fused))
        return fused

    # ── Fusion methods ────────────────────────────────────────────────────────────

    def _reciprocal_rank(
        self, lists: list[list[RankedItem]], weights: list[float]
    ) -> list[FusedResult]:
        acc: dict[str, dict] = {}
        for li, lst in enumerate(lists):
            for rank, item in enumerate(lst):
                contrib = weights[li] * (1.0 / (self.rrf_k + rank))
                self._accumulate(acc, item, contrib, source=f"list{li}")
        return self._finalize(acc)

    def _weighted_score(
        self, lists: list[list[RankedItem]], weights: list[float]
    ) -> list[FusedResult]:
        acc: dict[str, dict] = {}
        for li, lst in enumerate(lists):
            norms = _minmax_normalize([it.score for it in lst])
            for item, nscore in zip(lst, norms):
                contrib = weights[li] * nscore
                self._accumulate(acc, item, contrib, source=f"list{li}")
        return self._finalize(acc)

    @staticmethod
    def _accumulate(acc: dict, item: RankedItem, contrib: float, *, source: str) -> None:
        entry = acc.get(item.doc_id)
        if entry is None:
            acc[item.doc_id] = {
                "score": contrib,
                "sources": [source],
                "text": item.text,
                "metadata": item.metadata,
            }
        else:
            entry["score"] += contrib
            entry["sources"].append(source)
            # keep first non-empty text/metadata
            if not entry["text"] and item.text:
                entry["text"] = item.text
            if not entry["metadata"] and item.metadata:
                entry["metadata"] = item.metadata

    @staticmethod
    def _finalize(acc: dict) -> list[FusedResult]:
        return [
            FusedResult(
                doc_id=doc_id,
                fused_score=round(data["score"], 6),
                rank=0,
                sources=data["sources"],
                text=data["text"],
                metadata=data["metadata"],
            )
            for doc_id, data in acc.items()
        ]

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def _record(self, inputs: int, outputs: int) -> None:
        with self._lock:
            self._total_fusions += 1
            self._total_inputs += inputs
            self._total_outputs += outputs

    def metrics(self) -> dict:
        with self._lock:
            fusions = self._total_fusions
            return {
                "total_fusions": fusions,
                "total_input_items": self._total_inputs,
                "total_output_items": self._total_outputs,
                "avg_output_size": round(self._total_outputs / fusions, 4)
                if fusions else 0.0,
                "rrf_k": self.rrf_k,
                "default_method": self.default_method.value,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total_fusions = 0
            self._total_inputs = 0
            self._total_outputs = 0
