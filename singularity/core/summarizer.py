"""
Singularity — Extractive Summarizer (Fáze 42).

Frequency-based extractive summarization. Sentences are scored by the sum of
their (stopword-filtered) word frequencies, normalized by sentence length to
avoid favoring long sentences; the top-ranked sentences are returned in their
original order. Useful for TL;DR generation and memory compression without an
LLM call.

Dependency-free and deterministic — no embeddings, no network.
"""

from __future__ import annotations

import math
import re
import threading
from collections import Counter
from dataclasses import dataclass, field


_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "of", "to", "in", "on", "at", "for", "and", "or", "but", "with", "as",
    "by", "that", "this", "these", "those", "it", "its", "from", "has", "have",
    "had", "do", "does", "did", "will", "would", "can", "could", "should",
    "i", "you", "he", "she", "we", "they", "them", "his", "her", "their",
    "not", "no", "so", "if", "then", "than", "too", "very", "just",
})

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[a-z0-9']+")


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_SPLIT.split((text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def _content_words(sentence: str) -> list[str]:
    return [w for w in _WORD.findall(sentence.lower()) if w not in _STOPWORDS]


# ── Result ──────────────────────────────────────────────────────────────────────

@dataclass
class SummaryResult:
    summary: str
    selected_indices: list[int] = field(default_factory=list)
    original_sentences: int = 0
    summary_sentences: int = 0
    compression_ratio: float = 0.0   # summary_sentences / original_sentences
    keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "summary": self.summary,
            "selected_indices": self.selected_indices,
            "original_sentences": self.original_sentences,
            "summary_sentences": self.summary_sentences,
            "compression_ratio": self.compression_ratio,
            "keywords": self.keywords,
        }


# ── Summarizer ──────────────────────────────────────────────────────────────────

class ExtractiveSummarizer:
    """
    Select the most salient sentences from a text.

    ``ratio`` (0,1] picks ceil(ratio × N) sentences; ``max_sentences`` caps
    the count. The higher-priority bound wins (the smaller resulting count).
    """

    def __init__(self, *, ratio: float = 0.3, max_sentences: int | None = None) -> None:
        if not 0.0 < ratio <= 1.0:
            raise ValueError("ratio must be in (0.0, 1.0]")
        if max_sentences is not None and max_sentences < 1:
            raise ValueError("max_sentences must be >= 1")
        self.ratio = ratio
        self.max_sentences = max_sentences
        self._lock = threading.Lock()

        # metrics
        self._total_summaries = 0
        self._total_in_sentences = 0
        self._total_out_sentences = 0

    def summarize(
        self,
        text: str,
        *,
        ratio: float | None = None,
        max_sentences: int | None = None,
        top_keywords: int = 5,
    ) -> SummaryResult:
        r = ratio if ratio is not None else self.ratio
        if not 0.0 < r <= 1.0:
            raise ValueError("ratio must be in (0.0, 1.0]")
        cap = max_sentences if max_sentences is not None else self.max_sentences

        sentences = _split_sentences(text)
        n = len(sentences)
        if n == 0:
            self._record(0, 0)
            return SummaryResult(summary="", original_sentences=0,
                                 summary_sentences=0, compression_ratio=0.0)

        # Corpus word frequencies (normalized to max).
        freq: Counter[str] = Counter()
        for s in sentences:
            freq.update(_content_words(s))
        if freq:
            max_f = max(freq.values())
            norm_freq = {w: c / max_f for w, c in freq.items()}
        else:
            norm_freq = {}

        # Score each sentence: sum of normalized word freqs / sqrt(length).
        scores: list[float] = []
        for s in sentences:
            words = _content_words(s)
            if not words:
                scores.append(0.0)
                continue
            raw = sum(norm_freq.get(w, 0.0) for w in words)
            scores.append(raw / math.sqrt(len(words)))

        # How many to keep.
        keep = max(1, math.ceil(r * n))
        if cap is not None:
            keep = min(keep, cap)
        keep = min(keep, n)

        # Pick top-`keep` by score (tie-break: earlier sentence), then restore order.
        ranked = sorted(range(n), key=lambda i: (-scores[i], i))
        chosen = sorted(ranked[:keep])
        summary = " ".join(sentences[i] for i in chosen)

        keywords = [w for w, _ in freq.most_common(top_keywords)]

        self._record(n, len(chosen))
        return SummaryResult(
            summary=summary,
            selected_indices=chosen,
            original_sentences=n,
            summary_sentences=len(chosen),
            compression_ratio=round(len(chosen) / n, 4),
            keywords=keywords,
        )

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def _record(self, in_n: int, out_n: int) -> None:
        with self._lock:
            self._total_summaries += 1
            self._total_in_sentences += in_n
            self._total_out_sentences += out_n

    def metrics(self) -> dict:
        with self._lock:
            ins = self._total_in_sentences
            return {
                "total_summaries": self._total_summaries,
                "total_input_sentences": ins,
                "total_output_sentences": self._total_out_sentences,
                "overall_compression": round(self._total_out_sentences / ins, 4)
                if ins else 0.0,
                "ratio": self.ratio,
                "max_sentences": self.max_sentences,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total_summaries = 0
            self._total_in_sentences = 0
            self._total_out_sentences = 0
