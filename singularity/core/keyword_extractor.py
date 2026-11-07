"""
Singularity — Keyword Extractor (Fáze 46).

RAKE-style (Rapid Automatic Keyword Extraction) keyphrase extraction.
Candidate phrases are the runs of words between stopwords / punctuation.
Each word gets a score = degree / frequency (degree = total co-occurrence
length across phrases it appears in); a phrase score is the sum of its word
scores. The top phrases are returned as keywords.

Dependency-free and deterministic — no models, no network.
"""

from __future__ import annotations

import re
import threading
from collections import defaultdict
from dataclasses import dataclass, field


_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "of", "to", "in", "on", "at", "for", "and", "or", "but", "with", "as",
    "by", "that", "this", "these", "those", "it", "its", "from", "has", "have",
    "had", "do", "does", "did", "will", "would", "can", "could", "should",
    "i", "you", "he", "she", "we", "they", "them", "his", "her", "their",
    "not", "no", "so", "if", "then", "than", "too", "very", "just", "about",
    "into", "over", "after", "more", "most", "such", "some", "any", "all",
    "what", "which", "who", "when", "where", "how", "why", "there", "here",
})

# Split on anything that is not a word character; sentence delimiters break phrases.
_TOKEN = re.compile(r"[a-z0-9']+")
_PHRASE_BREAK = re.compile(r"[.,;:!?()\[\]{}\"]")


# ── Result ──────────────────────────────────────────────────────────────────────

@dataclass
class Keyword:
    phrase: str
    score: float

    def to_dict(self) -> dict:
        return {"phrase": self.phrase, "score": self.score}


@dataclass
class KeywordResult:
    keywords: list[Keyword] = field(default_factory=list)
    candidate_count: int = 0
    word_count: int = 0

    def to_dict(self) -> dict:
        return {
            "keywords": [k.to_dict() for k in self.keywords],
            "candidate_count": self.candidate_count,
            "word_count": self.word_count,
        }


# ── Extractor ───────────────────────────────────────────────────────────────────

class KeywordExtractor:
    """
    Extract keyphrases via the RAKE algorithm.

    ``max_phrase_words`` drops over-long candidate phrases (usually noise);
    ``min_word_length`` ignores very short tokens.
    """

    def __init__(
        self,
        *,
        max_phrase_words: int = 4,
        min_word_length: int = 2,
        stopwords: frozenset[str] | None = None,
    ) -> None:
        if max_phrase_words < 1:
            raise ValueError("max_phrase_words must be >= 1")
        if min_word_length < 1:
            raise ValueError("min_word_length must be >= 1")
        self.max_phrase_words = max_phrase_words
        self.min_word_length = min_word_length
        self._stopwords = stopwords if stopwords is not None else _STOPWORDS
        self._lock = threading.Lock()

        # metrics
        self._total = 0
        self._total_keywords = 0

    # ── Phrase generation ─────────────────────────────────────────────────────────

    def _candidate_phrases(self, text: str) -> list[list[str]]:
        phrases: list[list[str]] = []
        # Break on sentence punctuation first.
        for segment in _PHRASE_BREAK.split((text or "").lower()):
            current: list[str] = []
            for tok in _TOKEN.findall(segment):
                if tok in self._stopwords or len(tok) < self.min_word_length:
                    if current:
                        phrases.append(current)
                        current = []
                else:
                    current.append(tok)
            if current:
                phrases.append(current)
        # Drop over-long phrases.
        return [p for p in phrases if 1 <= len(p) <= self.max_phrase_words]

    # ── Extraction ────────────────────────────────────────────────────────────────

    def extract(self, text: str, *, top_k: int = 10) -> KeywordResult:
        if top_k < 1:
            raise ValueError("top_k must be >= 1")

        word_count = len(_TOKEN.findall((text or "").lower()))
        phrases = self._candidate_phrases(text)
        if not phrases:
            self._record(0)
            return KeywordResult(keywords=[], candidate_count=0, word_count=word_count)

        # Word frequency and degree.
        freq: dict[str, int] = defaultdict(int)
        degree: dict[str, int] = defaultdict(int)
        for phrase in phrases:
            plen = len(phrase)
            for w in phrase:
                freq[w] += 1
                degree[w] += plen  # includes self → degree = co-occurrence + freq
        # Word score = degree / freq.
        word_score = {w: degree[w] / freq[w] for w in freq}

        # Phrase score = sum of word scores; dedup by phrase text keeping max.
        phrase_scores: dict[str, float] = {}
        for phrase in phrases:
            text_key = " ".join(phrase)
            score = round(sum(word_score[w] for w in phrase), 6)
            if score > phrase_scores.get(text_key, -1.0):
                phrase_scores[text_key] = score

        ranked = sorted(phrase_scores.items(), key=lambda kv: (-kv[1], kv[0]))
        keywords = [Keyword(phrase=p, score=s) for p, s in ranked[:top_k]]

        self._record(len(keywords))
        return KeywordResult(
            keywords=keywords,
            candidate_count=len(phrase_scores),
            word_count=word_count,
        )

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def _record(self, n_keywords: int) -> None:
        with self._lock:
            self._total += 1
            self._total_keywords += n_keywords

    def metrics(self) -> dict:
        with self._lock:
            n = self._total
            return {
                "total_extractions": n,
                "total_keywords": self._total_keywords,
                "avg_keywords": round(self._total_keywords / n, 4) if n else 0.0,
                "max_phrase_words": self.max_phrase_words,
                "min_word_length": self.min_word_length,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total = 0
            self._total_keywords = 0
