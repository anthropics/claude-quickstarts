"""
Singularity — Language Detector (Fáze 43).

Heuristic language identification using per-language stopword profiles. A
text is tokenized and scored against each language by the fraction of its
words that are known stopwords of that language; the best-scoring language
wins, with a confidence derived from its share of the total signal.

Covers English, Czech, German, French, Spanish out of the box; custom
profiles can be registered. Dependency-free and deterministic — no models,
no network.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field


_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text or "")]


# ── Stopword profiles ───────────────────────────────────────────────────────────

_PROFILES: dict[str, frozenset[str]] = {
    "en": frozenset({
        "the", "be", "to", "of", "and", "a", "in", "that", "have", "it",
        "for", "not", "on", "with", "as", "you", "do", "at", "this", "but",
        "his", "by", "from", "they", "we", "is", "are", "was", "what", "all",
    }),
    "cs": frozenset({
        "a", "se", "na", "že", "je", "to", "v", "s", "z", "do", "i", "o",
        "ale", "po", "jako", "za", "ve", "byl", "být", "jsem", "jsme", "tak",
        "který", "když", "nebo", "už", "co", "jeho", "této", "podle", "také",
    }),
    "de": frozenset({
        "der", "die", "und", "in", "den", "von", "zu", "das", "mit", "sich",
        "des", "auf", "für", "ist", "im", "dem", "nicht", "ein", "eine", "als",
        "auch", "es", "an", "werden", "aus", "er", "hat", "dass", "sie", "nach",
    }),
    "fr": frozenset({
        "le", "de", "un", "à", "être", "et", "en", "avoir", "que", "pour",
        "dans", "ce", "il", "qui", "ne", "sur", "se", "pas", "plus", "par",
        "je", "avec", "tout", "faire", "son", "mettre", "autre", "on", "mais", "nous",
    }),
    "es": frozenset({
        "de", "la", "que", "el", "en", "y", "a", "los", "del", "se", "las",
        "por", "un", "para", "con", "no", "una", "su", "al", "es", "lo",
        "como", "más", "pero", "sus", "le", "ya", "o", "porque", "muy",
    }),
}


# ── Result ──────────────────────────────────────────────────────────────────────

@dataclass
class LanguageResult:
    language: str
    confidence: float
    scores: dict[str, float] = field(default_factory=dict)
    word_count: int = 0
    matched_stopwords: int = 0

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "confidence": self.confidence,
            "scores": self.scores,
            "word_count": self.word_count,
            "matched_stopwords": self.matched_stopwords,
        }


# ── Detector ────────────────────────────────────────────────────────────────────

class LanguageDetector:
    """
    Detect the dominant language of a text.

    ``min_confidence`` below which detection falls back to ``unknown_label``.
    """

    def __init__(
        self,
        profiles: dict[str, frozenset[str]] | None = None,
        *,
        min_confidence: float = 0.0,
        unknown_label: str = "unknown",
    ) -> None:
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be in [0.0, 1.0]")
        self._profiles = dict(profiles) if profiles else dict(_PROFILES)
        self.min_confidence = min_confidence
        self.unknown_label = unknown_label
        self._lock = threading.Lock()

        # metrics
        self._total = 0
        self._by_language: dict[str, int] = {}
        self._unknowns = 0

    # ── Profile management ────────────────────────────────────────────────────────

    def register_profile(self, lang: str, stopwords: list[str]) -> None:
        with self._lock:
            self._profiles[lang] = frozenset(w.lower() for w in stopwords)

    def list_languages(self) -> list[str]:
        with self._lock:
            return sorted(self._profiles)

    # ── Detection ─────────────────────────────────────────────────────────────────

    def detect(self, text: str) -> LanguageResult:
        words = _tokenize(text)
        wc = len(words)

        with self._lock:
            profiles = dict(self._profiles)

        if wc == 0:
            self._record(self.unknown_label, unknown=True)
            return LanguageResult(self.unknown_label, 0.0, {}, 0, 0)

        # Count stopword hits per language.
        hits: dict[str, int] = {}
        for lang, stops in profiles.items():
            hits[lang] = sum(1 for w in words if w in stops)

        total_hits = sum(hits.values())
        if total_hits == 0:
            self._record(self.unknown_label, unknown=True)
            return LanguageResult(self.unknown_label, 0.0,
                                  {l: 0.0 for l in profiles}, wc, 0)

        # Score = language hits / total hits across languages (share of signal).
        scores = {lang: round(h / total_hits, 4) for lang, h in hits.items()}
        best = max(scores, key=lambda l: (scores[l], -sorted(profiles).index(l)))
        confidence = scores[best]
        matched = hits[best]

        if confidence < self.min_confidence:
            self._record(self.unknown_label, unknown=True)
            return LanguageResult(self.unknown_label, confidence, scores, wc, matched)

        self._record(best, unknown=False)
        return LanguageResult(best, confidence, scores, wc, matched)

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def _record(self, lang: str, *, unknown: bool) -> None:
        with self._lock:
            self._total += 1
            self._by_language[lang] = self._by_language.get(lang, 0) + 1
            if unknown:
                self._unknowns += 1

    def metrics(self) -> dict:
        with self._lock:
            n = self._total
            return {
                "total_detections": n,
                "by_language": dict(self._by_language),
                "unknowns": self._unknowns,
                "unknown_rate": round(self._unknowns / n, 4) if n else 0.0,
                "language_count": len(self._profiles),
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total = 0
            self._by_language = {}
            self._unknowns = 0
