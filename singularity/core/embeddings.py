"""
Singularity — Pluggable Embedding Provider (Fáze 61, v2.0).

Introduces an ``EmbeddingProvider`` abstraction so any component that needs
vectors (Semantic Cache Fáze 29, Retriever Fáze 37, Reranker Fáze 38) can be
backed by a real embedding model in production while staying fully offline and
deterministic in tests.

The default ``HashingEmbeddingProvider`` uses **feature hashing** over token
unigrams + bigrams: each feature is hashed to a dimension index and a sign,
and contributions accumulate into a fixed-size, L2-normalized vector. Unlike
the legacy whole-text sha hash (memory/embeddings.py), texts that share words
land on shared dimensions, so cosine similarity reflects real lexical overlap
— a meaningful quality upgrade for semantic caching.

A real API-backed provider can be dropped in by subclassing EmbeddingProvider;
``CachingEmbeddingProvider`` memoizes any inner provider. Dependency-free core.
"""

from __future__ import annotations

import hashlib
import math
import re
import threading
from abc import ABC, abstractmethod
from collections import OrderedDict


_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _WORD.findall((text or "").lower())


def _features(text: str, ngram: int) -> list[str]:
    toks = _tokens(text)
    feats = list(toks)
    for n in range(2, ngram + 1):
        if len(toks) >= n:
            feats.extend(" ".join(toks[i:i + n]) for i in range(len(toks) - n + 1))
    return feats


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two equal-length vectors; 0.0 on mismatch/zero."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


# ── Provider abstraction ─────────────────────────────────────────────────────────

class EmbeddingProvider(ABC):
    name: str = "abstract"

    @property
    @abstractmethod
    def dim(self) -> int: ...

    @abstractmethod
    def embed(self, text: str) -> list[float]: ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]

    def similarity(self, a: str, b: str) -> float:
        return cosine_similarity(self.embed(a), self.embed(b))

    def metrics(self) -> dict:
        return {"name": self.name, "dim": self.dim}


# ── Feature-hashing provider (default, offline) ──────────────────────────────────

class HashingEmbeddingProvider(EmbeddingProvider):
    """Deterministic feature-hashing embedder with lexical locality."""

    name = "hashing"

    def __init__(self, *, dim: int = 256, ngram: int = 2) -> None:
        if dim < 1:
            raise ValueError("dim must be >= 1")
        if ngram < 1:
            raise ValueError("ngram must be >= 1")
        self._dim = dim
        self.ngram = ngram
        self._lock = threading.Lock()
        self._embeds = 0

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        for feat in _features(text, self.ngram):
            h = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(h[:6], "big") % self._dim
            sign = 1.0 if (h[7] & 1) else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(x * x for x in vec))
        with self._lock:
            self._embeds += 1
        if norm == 0.0:
            return vec
        return [x / norm for x in vec]

    def metrics(self) -> dict:
        with self._lock:
            return {"name": self.name, "dim": self._dim, "ngram": self.ngram,
                    "embeds": self._embeds}


# ── Caching wrapper ──────────────────────────────────────────────────────────────

class CachingEmbeddingProvider(EmbeddingProvider):
    """LRU-memoizes an inner provider's per-text embeddings."""

    def __init__(self, inner: EmbeddingProvider, *, max_size: int = 1000) -> None:
        if max_size < 1:
            raise ValueError("max_size must be >= 1")
        self.inner = inner
        self.name = f"cached:{inner.name}"
        self.max_size = max_size
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    @property
    def dim(self) -> int:
        return self.inner.dim

    def embed(self, text: str) -> list[float]:
        with self._lock:
            cached = self._cache.get(text)
            if cached is not None:
                self._cache.move_to_end(text)
                self._hits += 1
                return list(cached)
            self._misses += 1
        vec = self.inner.embed(text)
        with self._lock:
            self._cache[text] = vec
            self._cache.move_to_end(text)
            if len(self._cache) > self.max_size:
                self._cache.popitem(last=False)
        return list(vec)

    def metrics(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            return {
                "name": self.name, "dim": self.inner.dim,
                "cache_size": len(self._cache), "max_size": self.max_size,
                "hits": self._hits, "misses": self._misses,
                "hit_rate": round(self._hits / total, 4) if total else 0.0,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._hits = 0
            self._misses = 0


# ── Factory ──────────────────────────────────────────────────────────────────────

def build_embedding_provider(
    name: str = "hashing",
    *,
    dim: int = 256,
    ngram: int = 2,
    cache_size: int | None = 1000,
) -> EmbeddingProvider:
    """Construct a provider by name, optionally wrapped in an LRU cache."""
    if name in ("hashing", "hash", "default"):
        provider: EmbeddingProvider = HashingEmbeddingProvider(dim=dim, ngram=ngram)
    else:
        raise ValueError(f"Unknown embedding provider: {name!r}")
    if cache_size:
        return CachingEmbeddingProvider(provider, max_size=cache_size)
    return provider
