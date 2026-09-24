"""
Singularity — Fuzzy Matcher (Fáze 51).

Levenshtein-based fuzzy string matching for typo-tolerant lookups, command
resolution, and lightweight entity linking. Provides edit distance, a
normalized similarity ratio, and best/top-k search over a candidate list.

Distinct from the Deduplicator (Fáze 48, SimHash over token shingles): this
operates at character level on short strings. Dependency-free and
deterministic.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


def levenshtein(a: str, b: str) -> int:
    """Edit distance between two strings (insert/delete/substitute = 1)."""
    a = a or ""
    b = b or ""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    # two-row dynamic programming
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            cur[j] = min(
                prev[j] + 1,       # deletion
                cur[j - 1] + 1,    # insertion
                prev[j - 1] + cost,  # substitution
            )
        prev = cur
    return prev[-1]


def ratio(a: str, b: str) -> float:
    """Normalized similarity in [0, 1]: 1 − dist / max(len)."""
    a = a or ""
    b = b or ""
    if not a and not b:
        return 1.0
    m = max(len(a), len(b))
    if m == 0:
        return 1.0
    return 1.0 - levenshtein(a, b) / m


# ── Result ──────────────────────────────────────────────────────────────────────

@dataclass
class Match:
    candidate: str
    score: float
    distance: int

    def to_dict(self) -> dict:
        return {"candidate": self.candidate, "score": self.score,
                "distance": self.distance}


@dataclass
class MatchResult:
    query: str
    matches: list[Match] = field(default_factory=list)
    best: Match | None = None

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "matches": [m.to_dict() for m in self.matches],
            "best": self.best.to_dict() if self.best else None,
        }


# ── Matcher ─────────────────────────────────────────────────────────────────────

class FuzzyMatcher:
    """
    Fuzzy match a query against candidate strings.

    ``threshold`` is the minimum similarity ratio to count as a match;
    ``case_sensitive`` controls normalization. Candidates can be passed per
    call or preloaded once.
    """

    def __init__(
        self,
        candidates: list[str] | None = None,
        *,
        threshold: float = 0.6,
        case_sensitive: bool = False,
    ) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be in [0.0, 1.0]")
        self.threshold = threshold
        self.case_sensitive = case_sensitive
        self._candidates: list[str] = list(candidates or [])
        self._lock = threading.Lock()

        # metrics
        self._total_queries = 0
        self._hits = 0
        self._misses = 0

    # ── Candidate management ──────────────────────────────────────────────────────

    def set_candidates(self, candidates: list[str]) -> None:
        with self._lock:
            self._candidates = list(candidates)

    def list_candidates(self) -> list[str]:
        with self._lock:
            return list(self._candidates)

    def _norm(self, s: str) -> str:
        return (s or "") if self.case_sensitive else (s or "").lower()

    # ── Matching ──────────────────────────────────────────────────────────────────

    def match(
        self,
        query: str,
        candidates: list[str] | None = None,
        *,
        top_k: int = 5,
    ) -> MatchResult:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        with self._lock:
            pool = list(candidates) if candidates is not None else list(self._candidates)

        nq = self._norm(query)
        scored: list[Match] = []
        for cand in pool:
            nc = self._norm(cand)
            dist = levenshtein(nq, nc)
            score = round(ratio(nq, nc), 6)
            if score >= self.threshold:
                scored.append(Match(candidate=cand, score=score, distance=dist))

        scored.sort(key=lambda m: (-m.score, m.distance, m.candidate))
        top = scored[:top_k]
        best = top[0] if top else None

        with self._lock:
            self._total_queries += 1
            if best is not None:
                self._hits += 1
            else:
                self._misses += 1

        return MatchResult(query=query, matches=top, best=best)

    def best_match(self, query: str, candidates: list[str] | None = None) -> Match | None:
        return self.match(query, candidates, top_k=1).best

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def metrics(self) -> dict:
        with self._lock:
            n = self._total_queries
            return {
                "total_queries": n,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / n, 4) if n else 0.0,
                "candidate_count": len(self._candidates),
                "threshold": self.threshold,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total_queries = 0
            self._hits = 0
            self._misses = 0
