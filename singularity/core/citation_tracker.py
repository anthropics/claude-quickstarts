"""
Singularity — Citation Tracker (Fáze 35).

Grounds an LLM response in a set of source documents. The response is split
into sentences; each sentence is matched against every source by token
overlap (Jaccard similarity). Sentences scoring above a threshold are
annotated with the supporting source(s); the rest are flagged as
unsupported — a cheap, dependency-free hallucination signal for RAG.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field


# ── Tokenization ────────────────────────────────────────────────────────────────

_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "of", "to", "in", "on", "at", "for", "and", "or", "but", "with", "as",
    "by", "that", "this", "these", "those", "it", "its", "from", "has", "have",
    "had", "do", "does", "did", "will", "would", "can", "could", "should",
})

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    words = _WORD.findall((text or "").lower())
    return {w for w in words if w not in _STOPWORDS}


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_SPLIT.split((text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


# ── Data structures ─────────────────────────────────────────────────────────────

@dataclass
class Source:
    source_id: str
    text: str


@dataclass
class SentenceCitation:
    sentence: str
    supported: bool
    best_score: float
    citations: list[dict] = field(default_factory=list)  # [{source_id, score}]

    def to_dict(self) -> dict:
        return {
            "sentence": self.sentence,
            "supported": self.supported,
            "best_score": self.best_score,
            "citations": self.citations,
        }


@dataclass
class CitationReport:
    sentences: list[SentenceCitation]
    total_sentences: int
    supported_sentences: int
    unsupported_sentences: int
    grounding_score: float          # supported / total
    used_sources: list[str]

    def to_dict(self) -> dict:
        return {
            "sentences": [s.to_dict() for s in self.sentences],
            "total_sentences": self.total_sentences,
            "supported_sentences": self.supported_sentences,
            "unsupported_sentences": self.unsupported_sentences,
            "grounding_score": self.grounding_score,
            "used_sources": self.used_sources,
        }


# ── Tracker ─────────────────────────────────────────────────────────────────────

class CitationTracker:
    """
    Annotates response sentences with supporting sources.

    A sentence is "supported" if its best Jaccard overlap with any source is
    >= ``threshold``. Up to ``max_citations`` top sources are attached per
    sentence (those also meeting the threshold).
    """

    def __init__(
        self,
        *,
        threshold: float = 0.2,
        max_citations: int = 3,
    ) -> None:
        if not 0.0 < threshold <= 1.0:
            raise ValueError("threshold must be in (0.0, 1.0]")
        if max_citations < 1:
            raise ValueError("max_citations must be >= 1")
        self.threshold = threshold
        self.max_citations = max_citations
        self._lock = threading.Lock()

        # metrics
        self._total_reports = 0
        self._total_sentences = 0
        self._total_supported = 0

    def track(
        self,
        response: str,
        sources: list[dict] | list[Source],
    ) -> CitationReport:
        norm_sources = self._normalize_sources(sources)
        source_tokens = {s.source_id: _tokens(s.text) for s in norm_sources}

        sentences = _split_sentences(response)
        results: list[SentenceCitation] = []
        used: set[str] = set()
        supported_count = 0

        for sent in sentences:
            sent_tok = _tokens(sent)
            scored = []
            for sid, stok in source_tokens.items():
                score = _jaccard(sent_tok, stok)
                if score >= self.threshold:
                    scored.append((sid, round(score, 4)))
            scored.sort(key=lambda x: (-x[1], x[0]))
            top = scored[: self.max_citations]
            best = top[0][1] if top else (
                round(max((_jaccard(sent_tok, t) for t in source_tokens.values()),
                          default=0.0), 4)
            )
            supported = bool(top)
            if supported:
                supported_count += 1
                used.update(sid for sid, _ in top)
            results.append(SentenceCitation(
                sentence=sent,
                supported=supported,
                best_score=best,
                citations=[{"source_id": sid, "score": sc} for sid, sc in top],
            ))

        total = len(sentences)
        grounding = round(supported_count / total, 4) if total else 0.0
        self._record(total, supported_count)

        return CitationReport(
            sentences=results,
            total_sentences=total,
            supported_sentences=supported_count,
            unsupported_sentences=total - supported_count,
            grounding_score=grounding,
            used_sources=sorted(used),
        )

    # ── Helpers ───────────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_sources(sources: list[dict] | list[Source]) -> list[Source]:
        out: list[Source] = []
        for i, s in enumerate(sources):
            if isinstance(s, Source):
                out.append(s)
            elif isinstance(s, dict):
                out.append(Source(
                    source_id=str(s.get("source_id", s.get("id", f"src{i}"))),
                    text=s.get("text", ""),
                ))
            else:
                out.append(Source(source_id=f"src{i}", text=str(s)))
        return out

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def _record(self, total: int, supported: int) -> None:
        with self._lock:
            self._total_reports += 1
            self._total_sentences += total
            self._total_supported += supported

    def metrics(self) -> dict:
        with self._lock:
            sents = self._total_sentences
            return {
                "total_reports": self._total_reports,
                "total_sentences": sents,
                "total_supported": self._total_supported,
                "overall_grounding": round(self._total_supported / sents, 4)
                if sents else 0.0,
                "threshold": self.threshold,
                "max_citations": self.max_citations,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total_reports = 0
            self._total_sentences = 0
            self._total_supported = 0
