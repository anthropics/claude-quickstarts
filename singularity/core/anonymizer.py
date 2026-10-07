"""
Singularity — PII Anonymizer (Fáze 39).

Reversible de-identification of personal data. Detects PII entities by
pattern, replaces each with a stable placeholder (e.g. ``[EMAIL_1]``), and
returns a mapping that can later restore the original text. Unlike the
pipeline's one-way PIIRedactionStep (Fáze 30), this preserves a token map so
a downstream LLM can operate on anonymized text and the original values can
be re-inserted into the response.

Dependency-free, deterministic: same input + same session yields the same
placeholders, so repeated occurrences of one value share a token.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from enum import Enum


# ── Entity types ────────────────────────────────────────────────────────────────

class PIIType(str, Enum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    SSN = "SSN"
    CREDIT_CARD = "CREDIT_CARD"
    IP = "IP"
    URL = "URL"


# Order matters: more specific patterns first so they win overlapping matches.
_PATTERNS: list[tuple[PIIType, re.Pattern]] = [
    (PIIType.EMAIL, re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")),
    (PIIType.URL, re.compile(r"https?://[^\s]+")),
    (PIIType.SSN, re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    (PIIType.CREDIT_CARD, re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")),
    (PIIType.IP, re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    (PIIType.PHONE, re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
]


# ── Result ──────────────────────────────────────────────────────────────────────

@dataclass
class AnonymizationResult:
    anonymized_text: str
    mapping: dict[str, str] = field(default_factory=dict)   # placeholder -> original
    entity_counts: dict[str, int] = field(default_factory=dict)

    @property
    def entity_count(self) -> int:
        return len(self.mapping)

    def to_dict(self) -> dict:
        return {
            "anonymized_text": self.anonymized_text,
            "mapping": self.mapping,
            "entity_counts": self.entity_counts,
            "entity_count": self.entity_count,
        }


# ── Anonymizer ──────────────────────────────────────────────────────────────────

class PIIAnonymizer:
    """
    Detect and reversibly replace PII.

    ``enabled_types`` restricts which entity kinds are processed (default:
    all). Each distinct original value gets one stable placeholder per call;
    restoring substitutes placeholders back to originals.
    """

    def __init__(self, *, enabled_types: list[PIIType] | None = None) -> None:
        self._enabled = set(enabled_types) if enabled_types else {t for t, _ in _PATTERNS}
        self._lock = threading.Lock()

        # metrics
        self._total_anonymized = 0
        self._total_entities = 0
        self._by_type: dict[str, int] = {}

    # ── Anonymize ───────────────────────────────────────────────────────────────

    def anonymize(self, text: str) -> AnonymizationResult:
        doc = text or ""
        mapping: dict[str, str] = {}          # placeholder -> original
        reverse: dict[str, str] = {}          # original -> placeholder (dedup)
        counters: dict[PIIType, int] = {}
        entity_counts: dict[str, int] = {}

        # Collect non-overlapping matches across all enabled patterns.
        spans: list[tuple[int, int, PIIType, str]] = []
        claimed: list[tuple[int, int]] = []

        for ptype, pattern in _PATTERNS:
            if ptype not in self._enabled:
                continue
            for m in pattern.finditer(doc):
                s, e = m.start(), m.end()
                if any(not (e <= cs or s >= ce) for cs, ce in claimed):
                    continue  # overlaps an already-claimed span
                spans.append((s, e, ptype, m.group()))
                claimed.append((s, e))

        # Apply replacements left-to-right (rebuild string).
        spans.sort(key=lambda x: x[0])
        out = []
        cursor = 0
        for s, e, ptype, original in spans:
            out.append(doc[cursor:s])
            if original in reverse:
                placeholder = reverse[original]
            else:
                counters[ptype] = counters.get(ptype, 0) + 1
                placeholder = f"[{ptype.value}_{counters[ptype]}]"
                reverse[original] = placeholder
                mapping[placeholder] = original
                entity_counts[ptype.value] = entity_counts.get(ptype.value, 0) + 1
            out.append(placeholder)
            cursor = e
        out.append(doc[cursor:])

        self._record(len(mapping), entity_counts)
        return AnonymizationResult(
            anonymized_text="".join(out),
            mapping=mapping,
            entity_counts=entity_counts,
        )

    # ── Restore ───────────────────────────────────────────────────────────────────

    @staticmethod
    def restore(text: str, mapping: dict[str, str]) -> str:
        """Re-insert original values. Longer placeholders first to avoid
        partial overlaps (e.g. [EMAIL_1] vs [EMAIL_11])."""
        restored = text or ""
        for placeholder in sorted(mapping, key=len, reverse=True):
            restored = restored.replace(placeholder, mapping[placeholder])
        return restored

    # ── Detection only ─────────────────────────────────────────────────────────────

    def detect(self, text: str) -> list[dict]:
        """Return detected entities without modifying text."""
        doc = text or ""
        found: list[dict] = []
        claimed: list[tuple[int, int]] = []
        for ptype, pattern in _PATTERNS:
            if ptype not in self._enabled:
                continue
            for m in pattern.finditer(doc):
                s, e = m.start(), m.end()
                if any(not (e <= cs or s >= ce) for cs, ce in claimed):
                    continue
                claimed.append((s, e))
                found.append({"type": ptype.value, "value": m.group(),
                              "start": s, "end": e})
        found.sort(key=lambda x: x["start"])
        return found

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def _record(self, n_entities: int, by_type: dict[str, int]) -> None:
        with self._lock:
            self._total_anonymized += 1
            self._total_entities += n_entities
            for k, v in by_type.items():
                self._by_type[k] = self._by_type.get(k, 0) + v

    def metrics(self) -> dict:
        with self._lock:
            calls = self._total_anonymized
            return {
                "total_anonymized": calls,
                "total_entities": self._total_entities,
                "by_type": dict(self._by_type),
                "avg_entities_per_call": round(self._total_entities / calls, 4)
                if calls else 0.0,
                "enabled_types": sorted(t.value for t in self._enabled),
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total_anonymized = 0
            self._total_entities = 0
            self._by_type = {}
