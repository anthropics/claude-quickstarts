"""
Singularity — Semantic Cache (Fáze 29).

Extends exact-match LRU caching with embedding-based cosine-similarity lookup.
Near-duplicate queries (above a configurable threshold) are served from cache
without calling the LLM, significantly reducing API cost and latency.

The embedding function is injectable, making this module fully offline-testable:
- Tests inject a deterministic vector function.
- Production injects a real embedding model (e.g. text-embedding-3-small).

Hit taxonomy:
  EXACT   — identical text (fast hash lookup, O(1))
  SEMANTIC — cosine similarity ≥ threshold (linear scan, O(n))
  MISS    — no entry above threshold
"""
from __future__ import annotations

import math
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

import structlog

log = structlog.get_logger()

# Embedding function type: text → float vector
EmbedFn = Callable[[str], list[float]]


# ── Enums & result types ──────────────────────────────────────────────────────

class HitType(str, Enum):
    EXACT = "exact"
    SEMANTIC = "semantic"
    MISS = "miss"


@dataclass
class SemanticCacheResult:
    hit_type: HitType
    response: str
    similarity: float               # 1.0 for EXACT, cosine score for SEMANTIC
    matched_text: str               # the cached query text that matched
    entry_id: str

    def to_dict(self) -> dict:
        return {
            "hit_type": self.hit_type.value,
            "response": self.response,
            "similarity": round(self.similarity, 4),
            "matched_text": self.matched_text,
            "entry_id": self.entry_id,
        }


# ── Internal entry ────────────────────────────────────────────────────────────

@dataclass
class _Entry:
    entry_id: str
    text: str
    embedding: list[float]
    response: str
    created_at: float               # monotonic timestamp
    ttl_s: float
    hits: int = 0

    def is_expired(self) -> bool:
        return time.monotonic() - self.created_at > self.ttl_s


# ── Cosine similarity (pure Python, no numpy) ─────────────────────────────────

def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ── SemanticCache ─────────────────────────────────────────────────────────────

class SemanticCache:
    """
    Thread-safe semantic cache with exact + cosine-similarity lookup.

    Usage:
        embed = lambda text: my_model.encode(text)
        cache = SemanticCache(embed_fn=embed, threshold=0.95)

        cache.put("What is the capital of France?", "Paris")
        result = cache.get("Capital of France?")
        # result.hit_type == HitType.SEMANTIC
    """

    def __init__(
        self,
        embed_fn: EmbedFn,
        *,
        threshold: float = 0.95,
        max_size: int = 500,
        ttl_s: float = 300.0,
    ) -> None:
        if not (0.0 < threshold <= 1.0):
            raise ValueError("threshold must be in (0.0, 1.0]")
        if max_size < 1:
            raise ValueError("max_size must be >= 1")
        if ttl_s <= 0:
            raise ValueError("ttl_s must be > 0")

        self._embed_fn = embed_fn
        self.threshold = threshold
        self.max_size = max_size
        self.ttl_s = ttl_s

        # Ordered dict gives O(1) LRU: move-to-end on hit, popitem(last=False) on evict
        self._store: OrderedDict[str, _Entry] = OrderedDict()
        # Secondary exact-lookup index: normalized text → entry_id
        self._text_index: dict[str, str] = {}
        self._lock = threading.Lock()

        # Stats
        self._total_queries = 0
        self._exact_hits = 0
        self._semantic_hits = 0
        self._misses = 0
        self._evictions = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def put(self, text: str, response: str) -> str:
        """
        Store a text→response pair. Returns entry_id.
        If text is already cached (exact match), updates the response and resets TTL.
        Evicts the least-recently-used entry when max_size is reached.
        """
        norm = _normalize(text)
        embedding = self._embed_fn(text)
        now = time.monotonic()

        with self._lock:
            # Update existing exact entry
            if norm in self._text_index:
                eid = self._text_index[norm]
                if eid in self._store:
                    entry = self._store[eid]
                    entry.response = response
                    entry.embedding = embedding
                    entry.created_at = now
                    entry.hits = 0
                    self._store.move_to_end(eid)
                    return eid

            # Evict if full
            while len(self._store) >= self.max_size:
                _, evicted = self._store.popitem(last=False)
                self._text_index.pop(_normalize(evicted.text), None)
                self._evictions += 1

            eid = str(uuid.uuid4())
            self._store[eid] = _Entry(
                entry_id=eid,
                text=text,
                embedding=embedding,
                response=response,
                created_at=now,
                ttl_s=self.ttl_s,
            )
            self._text_index[norm] = eid

        log.debug("semantic_cache_put", entry_id=eid, text_len=len(text))
        return eid

    def get(self, text: str) -> SemanticCacheResult | None:
        """
        Lookup text in cache.

        1. Exact match (normalized text equality) — fastest path.
        2. Cosine similarity scan across non-expired entries.
        Returns None on miss. Expired entries are pruned lazily during scan.
        """
        norm = _normalize(text)
        embedding = self._embed_fn(text)

        with self._lock:
            self._total_queries += 1

            # ── 1. Exact match ──────────────────────────────────────────────
            if norm in self._text_index:
                eid = self._text_index[norm]
                entry = self._store.get(eid)
                if entry and not entry.is_expired():
                    entry.hits += 1
                    self._store.move_to_end(eid)
                    self._exact_hits += 1
                    return SemanticCacheResult(
                        hit_type=HitType.EXACT,
                        response=entry.response,
                        similarity=1.0,
                        matched_text=entry.text,
                        entry_id=eid,
                    )
                # Expired — remove
                if entry:
                    del self._store[eid]
                    self._text_index.pop(norm, None)

            # ── 2. Cosine similarity scan ───────────────────────────────────
            best_sim = -1.0
            best_entry: _Entry | None = None
            expired_ids: list[str] = []

            for eid, entry in self._store.items():
                if entry.is_expired():
                    expired_ids.append(eid)
                    continue
                sim = _cosine(embedding, entry.embedding)
                if sim > best_sim:
                    best_sim = sim
                    best_entry = entry

            # Lazy expiry cleanup
            for eid in expired_ids:
                e = self._store.pop(eid, None)
                if e:
                    self._text_index.pop(_normalize(e.text), None)

            if best_entry is not None and best_sim >= self.threshold:
                best_entry.hits += 1
                self._store.move_to_end(best_entry.entry_id)
                self._semantic_hits += 1
                return SemanticCacheResult(
                    hit_type=HitType.SEMANTIC,
                    response=best_entry.response,
                    similarity=best_sim,
                    matched_text=best_entry.text,
                    entry_id=best_entry.entry_id,
                )

            self._misses += 1
            return None

    def invalidate(self, text: str) -> bool:
        """Remove the exact entry for text. Returns True if found."""
        norm = _normalize(text)
        with self._lock:
            eid = self._text_index.pop(norm, None)
            if eid and eid in self._store:
                del self._store[eid]
                return True
        return False

    def clear(self) -> int:
        """Remove all entries. Returns number of entries cleared."""
        with self._lock:
            n = len(self._store)
            self._store.clear()
            self._text_index.clear()
        return n

    def entry_count(self) -> int:
        with self._lock:
            return len(self._store)

    def stats(self) -> dict:
        with self._lock:
            total = self._total_queries
            hits = self._exact_hits + self._semantic_hits
            return {
                "total_queries": total,
                "exact_hits": self._exact_hits,
                "semantic_hits": self._semantic_hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "hit_rate": round(hits / total, 4) if total else 0.0,
                "semantic_hit_rate": round(self._semantic_hits / total, 4) if total else 0.0,
                "entry_count": len(self._store),
                "threshold": self.threshold,
                "max_size": self.max_size,
                "ttl_s": self.ttl_s,
            }

    def reset_stats(self) -> None:
        with self._lock:
            self._total_queries = 0
            self._exact_hits = 0
            self._semantic_hits = 0
            self._misses = 0
            self._evictions = 0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Canonical form for exact-match lookup: lowercase + collapsed whitespace."""
    return " ".join(text.lower().split())
