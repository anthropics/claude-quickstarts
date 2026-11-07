"""
Singularity — Sentiment Analyzer (Fáze 45).

Lexicon-based sentiment scoring. Tokenizes text, sums polarity weights from
positive/negative word lists, and applies two contextual rules:

  - negation:    a negator ("not", "no", "never", "n't") within a small
                 window flips the polarity of the following sentiment word
  - intensifier: a booster ("very", "really", "extremely") scales the next
                 sentiment word's weight

The signed total is normalized to [-1, 1] and mapped to a POSITIVE / NEGATIVE
/ NEUTRAL label. Dependency-free and deterministic — no models, no network.
"""

from __future__ import annotations

import math
import re
import threading
from dataclasses import dataclass, field
from enum import Enum


class Polarity(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


_WORD = re.compile(r"[a-z']+")


def _tokenize(text: str) -> list[str]:
    return _WORD.findall((text or "").lower())


# ── Lexicons ────────────────────────────────────────────────────────────────────

_POSITIVE = {
    "good", "great", "excellent", "amazing", "wonderful", "fantastic",
    "love", "loved", "like", "liked", "happy", "best", "awesome", "nice",
    "perfect", "brilliant", "superb", "delightful", "pleased", "enjoy",
    "enjoyed", "helpful", "positive", "beautiful", "fast", "reliable",
    "recommend", "satisfied", "impressive", "outstanding",
}

_NEGATIVE = {
    "bad", "terrible", "awful", "horrible", "hate", "hated", "dislike",
    "worst", "poor", "disappointing", "disappointed", "sad", "angry",
    "broken", "useless", "slow", "buggy", "crash", "crashes", "annoying",
    "frustrating", "negative", "ugly", "unreliable", "fail", "failed",
    "wrong", "confusing", "difficult", "expensive",
}

_NEGATORS = {"not", "no", "never", "none", "n't", "without", "cannot", "cant"}

_INTENSIFIERS = {
    "very": 1.5, "really": 1.5, "extremely": 2.0, "so": 1.3,
    "absolutely": 1.8, "totally": 1.6, "incredibly": 1.8, "quite": 1.2,
}


# ── Result ──────────────────────────────────────────────────────────────────────

@dataclass
class SentimentResult:
    polarity: Polarity
    score: float                 # normalized [-1, 1]
    positive_hits: int = 0
    negative_hits: int = 0
    negations: int = 0
    word_count: int = 0
    tokens: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "polarity": self.polarity.value,
            "score": self.score,
            "positive_hits": self.positive_hits,
            "negative_hits": self.negative_hits,
            "negations": self.negations,
            "word_count": self.word_count,
        }


# ── Analyzer ────────────────────────────────────────────────────────────────────

class SentimentAnalyzer:
    """
    Score text sentiment with a lexicon plus negation/intensifier rules.

    ``threshold`` is the absolute normalized score above which a text is
    labeled positive/negative (otherwise neutral). ``negation_window`` is how
    many tokens back to look for a negator/intensifier.
    """

    def __init__(
        self,
        *,
        threshold: float = 0.05,
        negation_window: int = 2,
    ) -> None:
        if not 0.0 <= threshold < 1.0:
            raise ValueError("threshold must be in [0.0, 1.0)")
        if negation_window < 1:
            raise ValueError("negation_window must be >= 1")
        self.threshold = threshold
        self.negation_window = negation_window
        self._lock = threading.Lock()

        # metrics
        self._total = 0
        self._pos = 0
        self._neg = 0
        self._neu = 0

    def analyze(self, text: str) -> SentimentResult:
        tokens = _tokenize(text)
        n = len(tokens)
        if n == 0:
            self._record(Polarity.NEUTRAL)
            return SentimentResult(Polarity.NEUTRAL, 0.0, word_count=0, tokens=[])

        total = 0.0
        pos_hits = 0
        neg_hits = 0
        negations = 0

        for i, tok in enumerate(tokens):
            base = 0.0
            if tok in _POSITIVE:
                base = 1.0
                pos_hits += 1
            elif tok in _NEGATIVE:
                base = -1.0
                neg_hits += 1
            else:
                continue

            # look back within window for negators / intensifiers
            mult = 1.0
            negate = False
            lo = max(0, i - self.negation_window)
            for j in range(lo, i):
                prev = tokens[j]
                if prev in _NEGATORS:
                    negate = True
                if prev in _INTENSIFIERS:
                    mult *= _INTENSIFIERS[prev]
            if negate:
                base = -base
                negations += 1
            total += base * mult

        # Normalize with a soft saturation (tanh) → [-1, 1].
        score = round(math.tanh(total / 3.0), 6)

        if score >= self.threshold:
            polarity = Polarity.POSITIVE
        elif score <= -self.threshold:
            polarity = Polarity.NEGATIVE
        else:
            polarity = Polarity.NEUTRAL

        self._record(polarity)
        return SentimentResult(
            polarity=polarity,
            score=score,
            positive_hits=pos_hits,
            negative_hits=neg_hits,
            negations=negations,
            word_count=n,
            tokens=tokens,
        )

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def _record(self, polarity: Polarity) -> None:
        with self._lock:
            self._total += 1
            if polarity == Polarity.POSITIVE:
                self._pos += 1
            elif polarity == Polarity.NEGATIVE:
                self._neg += 1
            else:
                self._neu += 1

    def metrics(self) -> dict:
        with self._lock:
            n = self._total
            return {
                "total_analyses": n,
                "positive": self._pos,
                "negative": self._neg,
                "neutral": self._neu,
                "positive_rate": round(self._pos / n, 4) if n else 0.0,
                "negative_rate": round(self._neg / n, 4) if n else 0.0,
                "threshold": self.threshold,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total = 0
            self._pos = 0
            self._neg = 0
            self._neu = 0
