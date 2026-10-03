"""
Singularity — Readability Analyzer (Fáze 47).

Computes classic readability metrics for a text so callers can gauge — and
tune — how complex an LLM response is:

  - Flesch Reading Ease       (higher = easier; ~0–100)
  - Flesch-Kincaid Grade      (US school grade level)
  - avg words per sentence
  - avg syllables per word

Syllable counting is a heuristic vowel-group counter (no dictionary), good
enough for relative comparisons. Dependency-free and deterministic.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass

_SENTENCE_SPLIT = re.compile(r"[.!?]+")
_WORD = re.compile(r"[a-zA-Z]+")
_VOWEL_GROUP = re.compile(r"[aeiouy]+")


def _count_sentences(text: str) -> int:
    parts = [p for p in _SENTENCE_SPLIT.split(text or "") if p.strip()]
    return max(1, len(parts))


def _words(text: str) -> list[str]:
    return _WORD.findall(text or "")


def count_syllables(word: str) -> int:
    """Heuristic syllable count for an English word (>= 1)."""
    w = word.lower()
    if not w:
        return 0
    groups = _VOWEL_GROUP.findall(w)
    count = len(groups)
    # silent trailing 'e' (but not 'le' after a consonant, e.g. "table")
    if w.endswith("e") and not w.endswith("le") and count > 1:
        count -= 1
    return max(1, count)


# ── Result ──────────────────────────────────────────────────────────────────────

@dataclass
class ReadabilityResult:
    flesch_reading_ease: float
    flesch_kincaid_grade: float
    word_count: int
    sentence_count: int
    syllable_count: int
    avg_words_per_sentence: float
    avg_syllables_per_word: float
    reading_level: str

    def to_dict(self) -> dict:
        return {
            "flesch_reading_ease": self.flesch_reading_ease,
            "flesch_kincaid_grade": self.flesch_kincaid_grade,
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "syllable_count": self.syllable_count,
            "avg_words_per_sentence": self.avg_words_per_sentence,
            "avg_syllables_per_word": self.avg_syllables_per_word,
            "reading_level": self.reading_level,
        }


def _reading_level(ease: float) -> str:
    if ease >= 90:
        return "very_easy"
    if ease >= 70:
        return "easy"
    if ease >= 50:
        return "medium"
    if ease >= 30:
        return "difficult"
    return "very_difficult"


# ── Analyzer ────────────────────────────────────────────────────────────────────

class ReadabilityAnalyzer:
    """Compute Flesch readability metrics for arbitrary text."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # metrics
        self._total = 0
        self._sum_ease = 0.0
        self._sum_grade = 0.0

    def analyze(self, text: str) -> ReadabilityResult:
        words = _words(text)
        wc = len(words)

        if wc == 0:
            self._record(0.0, 0.0)
            return ReadabilityResult(
                flesch_reading_ease=0.0, flesch_kincaid_grade=0.0,
                word_count=0, sentence_count=0, syllable_count=0,
                avg_words_per_sentence=0.0, avg_syllables_per_word=0.0,
                reading_level="unknown",
            )

        sc = _count_sentences(text)
        syl = sum(count_syllables(w) for w in words)

        wps = wc / sc
        spw = syl / wc

        ease = round(206.835 - 1.015 * wps - 84.6 * spw, 2)
        grade = round(0.39 * wps + 11.8 * spw - 15.59, 2)

        self._record(ease, grade)
        return ReadabilityResult(
            flesch_reading_ease=ease,
            flesch_kincaid_grade=grade,
            word_count=wc,
            sentence_count=sc,
            syllable_count=syl,
            avg_words_per_sentence=round(wps, 2),
            avg_syllables_per_word=round(spw, 2),
            reading_level=_reading_level(ease),
        )

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def _record(self, ease: float, grade: float) -> None:
        with self._lock:
            self._total += 1
            self._sum_ease += ease
            self._sum_grade += grade

    def metrics(self) -> dict:
        with self._lock:
            n = self._total
            return {
                "total_analyses": n,
                "avg_reading_ease": round(self._sum_ease / n, 2) if n else 0.0,
                "avg_grade_level": round(self._sum_grade / n, 2) if n else 0.0,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total = 0
            self._sum_ease = 0.0
            self._sum_grade = 0.0
