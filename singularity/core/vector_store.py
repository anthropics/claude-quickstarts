"""
Singularity — Vector Store / Dense Retriever (Fáze 69, v2.0 #9).

An in-memory dense retriever: index documents by their embedding (via the
pluggable EmbeddingProvider, Fáze 61) and retrieve the top-k by cosine
similarity. This is the semantic counterpart to the lexical BM25 Retriever
(Fáze 37); the two can be fused by the Hybrid Reranker (Fáze 38) for
hybrid search.

Dependency-free (brute-force cosine k-NN) and deterministic offline with the
hashing embedding provider. A production deployment can swap the provider for
a real embedder and, at larger scale, this class for an ANN index behind the
same ``add`` / ``search`` surface.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from core.embeddings import EmbeddingProvider, build_embedding_provider, cosine_similarity


@dataclass
class VectorHit:
    doc_id: str
    score: float
    text: str
    rank: int
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"doc_id": self.doc_id, "score": self.score, "text": self.text,
                "rank": self.rank, "metadata": self.metadata}


@dataclass
class _Entry:
    doc_id: str
    text: str
    vector: list[float]
    metadata: dict


class VectorStore:
    """In-memory embedding index with cosine k-NN search."""

    def __init__(self, embedder: EmbeddingProvider | None = None) -> None:
        self._embedder = embedder or build_embedding_provider(cache_size=None)
        self._entries: dict[str, _Entry] = {}
        self._lock = threading.Lock()

        # metrics
        self._searches = 0
        self._total_hits = 0

    # ── Indexing ──────────────────────────────────────────────────────────────────

    def add(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        vec = self._embedder.embed(text)
        with self._lock:
            self._entries[str(doc_id)] = _Entry(str(doc_id), text, vec, metadata or {})

    def add_many(self, documents: list[dict]) -> int:
        n = 0
        for i, d in enumerate(documents):
            doc_id = d.get("doc_id", d.get("id", f"doc{i}"))
            self.add(doc_id, d.get("text", ""), d.get("metadata"))
            n += 1
        return n

    def remove(self, doc_id: str) -> bool:
        with self._lock:
            return self._entries.pop(str(doc_id), None) is not None

    def clear(self) -> int:
        with self._lock:
            n = len(self._entries)
            self._entries.clear()
            return n

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._entries)

    @property
    def dim(self) -> int:
        return self._embedder.dim

    # ── Search ────────────────────────────────────────────────────────────────────

    def search(self, query: str, *, top_k: int = 5,
               min_score: float = 0.0) -> list[VectorHit]:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        qv = self._embedder.embed(query)
        with self._lock:
            entries = list(self._entries.values())

        scored: list[tuple[float, _Entry]] = []
        for e in entries:
            s = cosine_similarity(qv, e.vector)
            if s > min_score:
                scored.append((s, e))
        scored.sort(key=lambda x: (-x[0], x[1].doc_id))
        top = scored[:top_k]

        hits = [
            VectorHit(doc_id=e.doc_id, score=round(s, 6), text=e.text,
                      rank=i, metadata=e.metadata)
            for i, (s, e) in enumerate(top)
        ]
        with self._lock:
            self._searches += 1
            self._total_hits += len(hits)
        return hits

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def metrics(self) -> dict:
        with self._lock:
            s = self._searches
            return {
                "indexed": len(self._entries),
                "dim": self._embedder.dim,
                "searches": s,
                "total_hits": self._total_hits,
                "avg_hits": round(self._total_hits / s, 4) if s else 0.0,
            }
