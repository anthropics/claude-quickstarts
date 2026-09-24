"""
Singularity — Intent Classifier (Fáze 34).

Lightweight, dependency-free classification of an incoming query into an
intent category using weighted keyword / regex signals. Each intent can
carry a routing hint (preferred provider) so callers can pick a model based
on *what kind* of request it is, complementing the strategy-based router.

Deterministic and offline: no embeddings, no network. Custom intents can be
registered at runtime.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field


# ── Data structures ─────────────────────────────────────────────────────────────

@dataclass
class IntentDefinition:
    name: str
    keywords: list[str] = field(default_factory=list)   # substring signals (weight 1.0)
    patterns: list[str] = field(default_factory=list)    # regex signals (weight 2.0)
    provider_hint: str | None = None
    weight: float = 1.0                                  # global multiplier

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "keywords": self.keywords,
            "patterns": self.patterns,
            "provider_hint": self.provider_hint,
            "weight": self.weight,
        }


@dataclass
class IntentResult:
    intent: str
    confidence: float
    provider_hint: str | None
    scores: dict[str, float] = field(default_factory=dict)
    matched_signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "provider_hint": self.provider_hint,
            "scores": self.scores,
            "matched_signals": self.matched_signals,
        }


# ── Built-in intents ─────────────────────────────────────────────────────────────

_KEYWORD_WEIGHT = 1.0
_PATTERN_WEIGHT = 2.0
_DEFAULT_INTENT = "general"


def _builtin_intents() -> list[IntentDefinition]:
    return [
        IntentDefinition(
            name="code",
            keywords=["function", "bug", "error", "compile", "python", "javascript",
                      "refactor", "debug", "stack trace", "exception", "api", "import"],
            patterns=[r"```", r"\bdef\b", r"\bclass\b", r"\b\w+\(\)", r"[{};]\s*$"],
            provider_hint="claude",
        ),
        IntentDefinition(
            name="math",
            keywords=["calculate", "solve", "equation", "derivative", "integral",
                      "probability", "sum", "product", "factorial"],
            patterns=[r"\d+\s*[\+\-\*/=]\s*\d+", r"\bx\^?\d?\b", r"\b\d+%"],
            provider_hint="claude",
        ),
        IntentDefinition(
            name="creative",
            keywords=["write a poem", "story", "imagine", "creative", "fiction",
                      "song", "lyrics", "brainstorm", "metaphor"],
            patterns=[r"\bwrite\b.{0,20}\b(poem|story|song|lyrics)\b"],
            provider_hint="gemini",
        ),
        IntentDefinition(
            name="factual",
            keywords=["what is", "who is", "when did", "where is", "define",
                      "explain", "how many", "capital of"],
            patterns=[r"^\s*(what|who|when|where|why|how)\b"],
            provider_hint="gemini",
        ),
        IntentDefinition(
            name="summarization",
            keywords=["summarize", "tl;dr", "summary", "key points", "in short",
                      "condense", "brief"],
            patterns=[r"\bsummari[sz]e\b"],
            provider_hint="gemini",
        ),
        IntentDefinition(
            name="translation",
            keywords=["translate", "in spanish", "in french", "in german",
                      "to english", "translation"],
            patterns=[r"\btranslate\b.*\b(to|into)\b"],
            provider_hint="gemini",
        ),
    ]


# ── Classifier ──────────────────────────────────────────────────────────────────

class IntentClassifier:
    """
    Scores a query against registered intents and returns the highest-scoring
    one. Confidence is the winning score divided by the total score across all
    intents (0.0 when nothing matched → falls back to the default intent).
    """

    def __init__(
        self,
        intents: list[IntentDefinition] | None = None,
        *,
        load_builtins: bool = True,
        default_intent: str = _DEFAULT_INTENT,
        min_confidence: float = 0.0,
    ) -> None:
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be in [0.0, 1.0]")
        self.default_intent = default_intent
        self.min_confidence = min_confidence
        self._intents: dict[str, IntentDefinition] = {}
        self._lock = threading.Lock()

        if load_builtins:
            for d in _builtin_intents():
                self._intents[d.name] = d
        for d in intents or []:
            self._intents[d.name] = d

        # metrics
        self._total = 0
        self._by_intent: dict[str, int] = {}
        self._fallbacks = 0

    # ── Intent management ──────────────────────────────────────────────────────

    def register(self, definition: IntentDefinition) -> None:
        with self._lock:
            self._intents[definition.name] = definition

    def unregister(self, name: str) -> bool:
        with self._lock:
            return self._intents.pop(name, None) is not None

    def list_intents(self) -> list[str]:
        with self._lock:
            return list(self._intents.keys())

    # ── Classification ─────────────────────────────────────────────────────────

    def classify(self, text: str) -> IntentResult:
        query = text or ""
        lowered = query.lower()

        with self._lock:
            intents = list(self._intents.values())

        scores: dict[str, float] = {}
        matched: dict[str, list[str]] = {}

        for intent in intents:
            score = 0.0
            sigs: list[str] = []
            for kw in intent.keywords:
                occurrences = lowered.count(kw.lower())
                if occurrences:
                    score += _KEYWORD_WEIGHT * occurrences
                    sigs.append(f"kw:{kw}")
            for pat in intent.patterns:
                try:
                    if re.search(pat, query, re.IGNORECASE | re.MULTILINE):
                        score += _PATTERN_WEIGHT
                        sigs.append(f"re:{pat}")
                except re.error:
                    continue
            score *= intent.weight
            if score > 0:
                scores[intent.name] = score
                matched[intent.name] = sigs

        if not scores:
            self._record(self.default_intent, fallback=True)
            return IntentResult(
                intent=self.default_intent,
                confidence=0.0,
                provider_hint=None,
                scores={},
                matched_signals=[],
            )

        total = sum(scores.values())
        # Winner: highest score, tie-break by registration order.
        best_name = max(
            scores,
            key=lambda n: (scores[n], -list(self._intents).index(n)),
        )
        confidence = round(scores[best_name] / total, 4)

        if confidence < self.min_confidence:
            self._record(self.default_intent, fallback=True)
            return IntentResult(
                intent=self.default_intent,
                confidence=confidence,
                provider_hint=None,
                scores=scores,
                matched_signals=matched.get(best_name, []),
            )

        hint = self._intents[best_name].provider_hint
        self._record(best_name, fallback=False)
        return IntentResult(
            intent=best_name,
            confidence=confidence,
            provider_hint=hint,
            scores=scores,
            matched_signals=matched.get(best_name, []),
        )

    # ── Metrics ─────────────────────────────────────────────────────────────────

    def _record(self, intent: str, *, fallback: bool) -> None:
        with self._lock:
            self._total += 1
            self._by_intent[intent] = self._by_intent.get(intent, 0) + 1
            if fallback:
                self._fallbacks += 1

    def metrics(self) -> dict:
        with self._lock:
            return {
                "total_classifications": self._total,
                "by_intent": dict(self._by_intent),
                "fallbacks": self._fallbacks,
                "fallback_rate": round(self._fallbacks / self._total, 4)
                if self._total else 0.0,
                "intent_count": len(self._intents),
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total = 0
            self._by_intent = {}
            self._fallbacks = 0
