"""
Singularity — BM25 Retriever (Fáze 37).

In-memory lexical retriever using Okapi BM25 ranking. Documents are indexed
by their tokenized content; a query is scored against every document and the
top-k are returned. Pairs naturally with the Document Chunker (Fáze 36) to
form a dependency-free RAG retrieval stage — no embeddings, no vector DB.

BM25 score for query Q over document D:

    score(D, Q) = Σ_t IDF(t) · ( f(t,D) · (k1+1) )
                              / ( f(t,D) + k1·(1 - b + b·|D|/avgdl) )

    IDF(t) = ln( (N - n(t) + 0.5) / (n(t) + 0.5) + 1 )

where f(t,D) is term frequency, |D| the doc length, avgdl the average
document length, N the corpus size, n(t) the document frequency of t.
"""

from __future__ import annotations

import math
import re
import threading
from dataclasses import dataclass, field


# ── Tokenization ────────────────────────────────────────────────────────────────

_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "of", "to", "in", "on", "at", "for", "and", "or", "but", "with", "as",
    "by", "that", "this", "these", "those", "it", "its", "from",
})

_WORD = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return [w for w in _WORD.findall((text or "").lower()) if w not in _STOPWORDS]


# ── Data structures ─────────────────────────────────────────────────────────────

@dataclass
class _Doc:
    doc_id: str
    text: str
    tokens: list[str]
    length: int
    tf: dict[str, int]
    metadata: dict = field(default_factory=dict)


@dataclass
class RetrievalHit:
    doc_id: str
    text: str
    score: float
    rank: int
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "text": self.text,
            "score": self.score,
            "rank": self.rank,
            "metadata": self.metadata,
        }


# ── Retriever ───────────────────────────────────────────────────────────────────

class BM25Retriever:
    """
    Add documents, then ``search`` for the top-k most relevant.

    ``k1`` controls term-frequency saturation (typical 1.2–2.0); ``b``
    controls length normalization (0 = none, 1 = full; typical 0.75).
    """

    def __init__(self, *, k1: float = 1.5, b: float = 0.75) -> None:
        if k1 < 0:
            raise ValueError("k1 must be >= 0")
        if not 0.0 <= b <= 1.0:
            raise ValueError("b must be in [0.0, 1.0]")
        self.k1 = k1
        self.b = b
        self._lock = threading.Lock()

        self._docs: dict[str, _Doc] = {}
        self._df: dict[str, int] = {}      # document frequency per term
        self._total_len = 0

        # metrics
        self._total_searches = 0
        self._total_hits_returned = 0

    # ── Indexing ──────────────────────────────────────────────────────────────────

    def add(self, doc_id: str, text: str, metadata: dict | None = None) -> None:
        tokens = _tokenize(text)
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        doc = _Doc(
            doc_id=str(doc_id), text=text, tokens=tokens,
            length=len(tokens), tf=tf, metadata=metadata or {},
        )
        with self._lock:
            if doc.doc_id in self._docs:
                self._remove_locked(doc.doc_id)
            self._docs[doc.doc_id] = doc
            self._total_len += doc.length
            for term in tf:
                self._df[term] = self._df.get(term, 0) + 1

    def add_many(self, documents: list[dict]) -> int:
        """Bulk add. Each dict: {doc_id/id, text, metadata?}. Returns count."""
        n = 0
        for i, d in enumerate(documents):
            doc_id = d.get("doc_id", d.get("id", f"doc{i}"))
            self.add(doc_id, d.get("text", ""), d.get("metadata"))
            n += 1
        return n

    def remove(self, doc_id: str) -> bool:
        with self._lock:
            return self._remove_locked(str(doc_id))

    def _remove_locked(self, doc_id: str) -> bool:
        doc = self._docs.pop(doc_id, None)
        if doc is None:
            return False
        self._total_len -= doc.length
        for term in doc.tf:
            if term in self._df:
                self._df[term] -= 1
                if self._df[term] <= 0:
                    del self._df[term]
        return True

    def clear(self) -> int:
        with self._lock:
            n = len(self._docs)
            self._docs.clear()
            self._df.clear()
            self._total_len = 0
            return n

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._docs)

    # ── Scoring ───────────────────────────────────────────────────────────────────

    def _idf(self, term: str, n_docs: int) -> float:
        df = self._df.get(term, 0)
        return math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)

    def search(self, query: str, *, top_k: int = 5) -> list[RetrievalHit]:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")
        q_terms = _tokenize(query)

        with self._lock:
            n_docs = len(self._docs)
            if n_docs == 0 or not q_terms:
                self._total_searches += 1
                return []
            avgdl = self._total_len / n_docs if n_docs else 0.0
            idf_cache = {t: self._idf(t, n_docs) for t in set(q_terms)}

            scored: list[tuple[str, float]] = []
            for doc_id, doc in self._docs.items():
                score = 0.0
                for t in q_terms:
                    f = doc.tf.get(t, 0)
                    if f == 0:
                        continue
                    denom = f + self.k1 * (1 - self.b + self.b * doc.length / avgdl)
                    score += idf_cache[t] * (f * (self.k1 + 1)) / denom
                if score > 0:
                    scored.append((doc_id, score))

            scored.sort(key=lambda x: (-x[1], x[0]))
            top = scored[:top_k]
            hits = [
                RetrievalHit(
                    doc_id=doc_id,
                    text=self._docs[doc_id].text,
                    score=round(score, 6),
                    rank=i,
                    metadata=self._docs[doc_id].metadata,
                )
                for i, (doc_id, score) in enumerate(top)
            ]
            self._total_searches += 1
            self._total_hits_returned += len(hits)
            return hits

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def metrics(self) -> dict:
        with self._lock:
            searches = self._total_searches
            return {
                "indexed_documents": len(self._docs),
                "vocabulary_size": len(self._df),
                "total_searches": searches,
                "total_hits_returned": self._total_hits_returned,
                "avg_hits_per_search": round(self._total_hits_returned / searches, 4)
                if searches else 0.0,
                "k1": self.k1,
                "b": self.b,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total_searches = 0
            self._total_hits_returned = 0
