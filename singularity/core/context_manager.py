"""
Singularity — Context Window Manager (Fáze 32).

Keeps a conversation history within a token budget. When messages exceed
the budget, a pluggable trimming strategy decides what to drop or compress
while always preserving system messages and the most recent turns.

Token counts use a lightweight word-based estimate (configurable factor)
so the module stays dependency-free and deterministic for offline tests.
A custom ``count_fn`` may be injected for real tokenizer parity.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


# ── Token counting ──────────────────────────────────────────────────────────────

TokenCountFn = Callable[[str], int]

_APPROX_FACTOR = 1.3


def estimate_tokens(text: str) -> int:
    """Word-count × 1.3, rounded. Deterministic, dependency-free."""
    return int(len((text or "").split()) * _APPROX_FACTOR)


# ── Strategy ────────────────────────────────────────────────────────────────────

class TrimStrategy(str, Enum):
    DROP_OLDEST = "drop_oldest"          # remove oldest non-system turns first
    SUMMARIZE_OLDEST = "summarize_oldest"  # replace dropped span with a summary note
    KEEP_RECENT = "keep_recent"          # hard keep only the last N turns


# ── Result ──────────────────────────────────────────────────────────────────────

@dataclass
class TrimResult:
    messages: list[dict]
    original_tokens: int
    final_tokens: int
    dropped_count: int
    summarized: bool
    strategy: TrimStrategy
    within_budget: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "messages": self.messages,
            "original_tokens": self.original_tokens,
            "final_tokens": self.final_tokens,
            "dropped_count": self.dropped_count,
            "summarized": self.summarized,
            "strategy": self.strategy.value,
            "within_budget": self.within_budget,
            "notes": self.notes,
        }


# ── Manager ─────────────────────────────────────────────────────────────────────

class ContextWindowManager:
    """
    Fits a message list into ``max_tokens``.

    System messages are always preserved. The ``keep_recent`` count guarantees
    that the most recent N non-system messages survive trimming (best-effort:
    if system + recent already exceed budget, they are still kept and
    within_budget will be False).
    """

    def __init__(
        self,
        *,
        max_tokens: int = 4000,
        keep_recent: int = 4,
        strategy: TrimStrategy = TrimStrategy.DROP_OLDEST,
        count_fn: TokenCountFn | None = None,
    ) -> None:
        if max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")
        if keep_recent < 0:
            raise ValueError("keep_recent must be >= 0")
        self.max_tokens = max_tokens
        self.keep_recent = keep_recent
        self.strategy = strategy
        self._count_fn = count_fn or estimate_tokens
        self._lock = threading.Lock()

        # metrics
        self._total_calls = 0
        self._total_trimmed = 0
        self._total_dropped = 0
        self._total_summarized = 0

    # ── Public API ──────────────────────────────────────────────────────────────

    def count_messages(self, messages: list[dict]) -> int:
        return sum(self._count_fn(m.get("content", "") or "") for m in messages)

    def fit(
        self,
        messages: list[dict],
        strategy: TrimStrategy | None = None,
    ) -> TrimResult:
        strat = strategy or self.strategy
        original = self.count_messages(messages)

        # Already fits → no-op.
        if original <= self.max_tokens:
            self._record(trimmed=False, dropped=0, summarized=False)
            return TrimResult(
                messages=list(messages),
                original_tokens=original,
                final_tokens=original,
                dropped_count=0,
                summarized=False,
                strategy=strat,
                within_budget=True,
                notes=["No trimming needed"],
            )

        if strat == TrimStrategy.KEEP_RECENT:
            result = self._keep_recent(messages, original, strat)
        elif strat == TrimStrategy.SUMMARIZE_OLDEST:
            result = self._drop_or_summarize(messages, original, strat, summarize=True)
        else:  # DROP_OLDEST
            result = self._drop_or_summarize(messages, original, strat, summarize=False)

        self._record(
            trimmed=result.dropped_count > 0 or result.summarized,
            dropped=result.dropped_count,
            summarized=result.summarized,
        )
        return result

    # ── Strategy implementations ──────────────────────────────────────────────────

    def _split(self, messages: list[dict]) -> tuple[list[int], list[int]]:
        """Return (system_indices, non_system_indices) preserving order."""
        sys_idx = [i for i, m in enumerate(messages) if m.get("role") == "system"]
        non_sys = [i for i, m in enumerate(messages) if m.get("role") != "system"]
        return sys_idx, non_sys

    def _drop_or_summarize(
        self,
        messages: list[dict],
        original: int,
        strat: TrimStrategy,
        *,
        summarize: bool,
    ) -> TrimResult:
        sys_idx, non_sys = self._split(messages)
        # Indices we must keep: all system + last `keep_recent` non-system.
        protected = set(sys_idx)
        protected.update(non_sys[-self.keep_recent:] if self.keep_recent else [])

        # Droppable = non-system, not protected, oldest first.
        droppable = [i for i in non_sys if i not in protected]

        kept = set(range(len(messages)))
        dropped: list[int] = []
        for i in droppable:
            if self.count_messages([messages[j] for j in sorted(kept)]) <= self.max_tokens:
                break
            kept.discard(i)
            dropped.append(i)

        kept_sorted = sorted(kept)
        new_messages = [messages[j] for j in kept_sorted]
        summarized = False
        notes: list[str] = []

        if dropped and summarize:
            # Insert a summary note where the first dropped message was, after system msgs.
            insert_pos = len([j for j in kept_sorted if messages[j].get("role") == "system"])
            summary_text = self._summarize([messages[j] for j in sorted(dropped)])
            new_messages.insert(
                insert_pos,
                {"role": "system", "content": summary_text},
            )
            summarized = True
            notes.append(f"Summarized {len(dropped)} dropped messages")
        elif dropped:
            notes.append(f"Dropped {len(dropped)} oldest messages")

        final = self.count_messages(new_messages)
        return TrimResult(
            messages=new_messages,
            original_tokens=original,
            final_tokens=final,
            dropped_count=len(dropped),
            summarized=summarized,
            strategy=strat,
            within_budget=final <= self.max_tokens,
            notes=notes or ["No droppable messages"],
        )

    def _keep_recent(
        self, messages: list[dict], original: int, strat: TrimStrategy
    ) -> TrimResult:
        sys_idx, non_sys = self._split(messages)
        keep_non_sys = set(non_sys[-self.keep_recent:] if self.keep_recent else [])
        kept_sorted = sorted(set(sys_idx) | keep_non_sys)
        new_messages = [messages[j] for j in kept_sorted]
        dropped = len(messages) - len(new_messages)
        final = self.count_messages(new_messages)
        return TrimResult(
            messages=new_messages,
            original_tokens=original,
            final_tokens=final,
            dropped_count=dropped,
            summarized=False,
            strategy=strat,
            within_budget=final <= self.max_tokens,
            notes=[f"Kept system + last {self.keep_recent} messages"],
        )

    @staticmethod
    def _summarize(dropped: list[dict]) -> str:
        """Cheap extractive summary: role + first 8 words of each dropped turn."""
        lines = []
        for m in dropped:
            role = m.get("role", "?")
            words = (m.get("content", "") or "").split()[:8]
            snippet = " ".join(words)
            lines.append(f"{role}: {snippet}…" if words else f"{role}: (empty)")
        return "[Earlier conversation summary]\n" + "\n".join(lines)

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def _record(self, *, trimmed: bool, dropped: int, summarized: bool) -> None:
        with self._lock:
            self._total_calls += 1
            if trimmed:
                self._total_trimmed += 1
            self._total_dropped += dropped
            if summarized:
                self._total_summarized += 1

    def metrics(self) -> dict:
        with self._lock:
            return {
                "total_calls": self._total_calls,
                "total_trimmed": self._total_trimmed,
                "total_dropped_messages": self._total_dropped,
                "total_summarized": self._total_summarized,
                "trim_rate": round(self._total_trimmed / self._total_calls, 4)
                if self._total_calls else 0.0,
                "max_tokens": self.max_tokens,
                "keep_recent": self.keep_recent,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total_calls = 0
            self._total_trimmed = 0
            self._total_dropped = 0
            self._total_summarized = 0
