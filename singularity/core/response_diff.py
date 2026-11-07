"""
Singularity — Response Comparator (Fáze 41).

Sentence-level diff between two LLM responses. Splits both into sentences,
aligns them with difflib, and classifies each segment as UNCHANGED, ADDED,
REMOVED, or CHANGED. Reports an overall similarity ratio plus token-level
Jaccard overlap — useful for A/B testing two prompts/models and for
regression detection between runs.

Dependency-free and deterministic.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum


# ── Segment kinds ───────────────────────────────────────────────────────────────

class DiffOp(str, Enum):
    UNCHANGED = "unchanged"
    ADDED = "added"       # present only in B
    REMOVED = "removed"   # present only in A
    CHANGED = "changed"   # replaced (A→B)


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[a-z0-9]+")


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_SPLIT.split((text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall((text or "").lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ── Data structures ─────────────────────────────────────────────────────────────

@dataclass
class DiffSegment:
    op: DiffOp
    a_text: str = ""
    b_text: str = ""

    def to_dict(self) -> dict:
        return {"op": self.op.value, "a_text": self.a_text, "b_text": self.b_text}


@dataclass
class DiffResult:
    segments: list[DiffSegment] = field(default_factory=list)
    similarity: float = 0.0          # SequenceMatcher ratio over sentences
    token_jaccard: float = 0.0       # token-set overlap of the whole texts
    added: int = 0
    removed: int = 0
    changed: int = 0
    unchanged: int = 0
    identical: bool = False

    def to_dict(self) -> dict:
        return {
            "segments": [s.to_dict() for s in self.segments],
            "similarity": self.similarity,
            "token_jaccard": self.token_jaccard,
            "added": self.added,
            "removed": self.removed,
            "changed": self.changed,
            "unchanged": self.unchanged,
            "identical": self.identical,
        }


# ── Comparator ──────────────────────────────────────────────────────────────────

class ResponseComparator:
    """Compute a sentence-level diff and similarity scores between two texts."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # metrics
        self._total_comparisons = 0
        self._identical_count = 0
        self._total_similarity = 0.0

    def compare(self, text_a: str, text_b: str) -> DiffResult:
        a_sents = _split_sentences(text_a)
        b_sents = _split_sentences(text_b)

        sm = SequenceMatcher(None, a_sents, b_sents)
        similarity = round(sm.ratio(), 6)
        token_jaccard = round(_jaccard(_tokens(text_a), _tokens(text_b)), 6)

        segments: list[DiffSegment] = []
        counts = {DiffOp.ADDED: 0, DiffOp.REMOVED: 0,
                  DiffOp.CHANGED: 0, DiffOp.UNCHANGED: 0}

        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for s in a_sents[i1:i2]:
                    segments.append(DiffSegment(DiffOp.UNCHANGED, a_text=s, b_text=s))
                    counts[DiffOp.UNCHANGED] += 1
            elif tag == "replace":
                # pair up replaced sentences as CHANGED; surplus become add/remove
                a_chunk = a_sents[i1:i2]
                b_chunk = b_sents[j1:j2]
                paired = min(len(a_chunk), len(b_chunk))
                for k in range(paired):
                    segments.append(DiffSegment(DiffOp.CHANGED,
                                                a_text=a_chunk[k], b_text=b_chunk[k]))
                    counts[DiffOp.CHANGED] += 1
                for s in a_chunk[paired:]:
                    segments.append(DiffSegment(DiffOp.REMOVED, a_text=s))
                    counts[DiffOp.REMOVED] += 1
                for s in b_chunk[paired:]:
                    segments.append(DiffSegment(DiffOp.ADDED, b_text=s))
                    counts[DiffOp.ADDED] += 1
            elif tag == "delete":
                for s in a_sents[i1:i2]:
                    segments.append(DiffSegment(DiffOp.REMOVED, a_text=s))
                    counts[DiffOp.REMOVED] += 1
            elif tag == "insert":
                for s in b_sents[j1:j2]:
                    segments.append(DiffSegment(DiffOp.ADDED, b_text=s))
                    counts[DiffOp.ADDED] += 1

        identical = (text_a or "") == (text_b or "")
        self._record(similarity, identical)

        return DiffResult(
            segments=segments,
            similarity=similarity,
            token_jaccard=token_jaccard,
            added=counts[DiffOp.ADDED],
            removed=counts[DiffOp.REMOVED],
            changed=counts[DiffOp.CHANGED],
            unchanged=counts[DiffOp.UNCHANGED],
            identical=identical,
        )

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def _record(self, similarity: float, identical: bool) -> None:
        with self._lock:
            self._total_comparisons += 1
            self._total_similarity += similarity
            if identical:
                self._identical_count += 1

    def metrics(self) -> dict:
        with self._lock:
            n = self._total_comparisons
            return {
                "total_comparisons": n,
                "identical_count": self._identical_count,
                "avg_similarity": round(self._total_similarity / n, 6) if n else 0.0,
                "identical_rate": round(self._identical_count / n, 6) if n else 0.0,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total_comparisons = 0
            self._identical_count = 0
            self._total_similarity = 0.0
