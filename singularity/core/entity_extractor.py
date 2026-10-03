"""
Singularity — Entity Extractor (Fáze 49).

Pattern-based named-entity recognition. Pulls structured entities out of free
text — dates, money amounts, percentages, emails, URLs, phone numbers, and
capitalized proper-noun spans — with their character offsets. Unlike the PII
Anonymizer (Fáze 39, which masks for privacy), this classifies and surfaces
entities for downstream structuring / extraction.

Dependency-free and deterministic — pure regex, no models.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from enum import Enum


class EntityType(str, Enum):
    DATE = "DATE"
    MONEY = "MONEY"
    PERCENT = "PERCENT"
    EMAIL = "EMAIL"
    URL = "URL"
    PHONE = "PHONE"
    NUMBER = "NUMBER"
    PROPER_NOUN = "PROPER_NOUN"


_MONTHS = (
    r"(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
)

# Order: most specific first so overlaps resolve sensibly.
_PATTERNS: list[tuple[EntityType, re.Pattern]] = [
    (EntityType.EMAIL, re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")),
    (EntityType.URL, re.compile(r"https?://[^\s]+")),
    (EntityType.DATE, re.compile(
        rf"\b(?:{_MONTHS}\.?\s+\d{{1,2}}(?:,?\s+\d{{4}})?|"
        rf"\d{{1,2}}\s+{_MONTHS}\.?\s+\d{{4}}|"
        rf"\d{{4}}-\d{{2}}-\d{{2}}|\d{{1,2}}/\d{{1,2}}/\d{{2,4}})\b",
        re.IGNORECASE,
    )),
    (EntityType.MONEY, re.compile(
        r"(?:[$€£¥]\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:million|billion|thousand|k|m|bn))?|"
        r"\d[\d,]*(?:\.\d+)?\s?(?:million|billion|thousand)?\s?"
        r"(?:USD|EUR|GBP|dollars|euros|pounds))",
        re.IGNORECASE,
    )),
    (EntityType.PERCENT, re.compile(r"\b\d+(?:\.\d+)?\s?%")),
    (EntityType.PHONE, re.compile(
        r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b")),
    (EntityType.PROPER_NOUN, re.compile(
        r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b")),
    (EntityType.NUMBER, re.compile(r"\b\d+(?:\.\d+)?\b")),
]


# ── Result ──────────────────────────────────────────────────────────────────────

@dataclass
class Entity:
    type: str
    value: str
    start: int
    end: int

    def to_dict(self) -> dict:
        return {"type": self.type, "value": self.value,
                "start": self.start, "end": self.end}


@dataclass
class EntityResult:
    entities: list[Entity] = field(default_factory=list)
    counts_by_type: dict[str, int] = field(default_factory=dict)

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    def to_dict(self) -> dict:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "counts_by_type": self.counts_by_type,
            "entity_count": self.entity_count,
        }


# ── Extractor ───────────────────────────────────────────────────────────────────

class EntityExtractor:
    """
    Extract typed entities with offsets. ``enabled_types`` restricts which
    kinds are returned (default: all). Overlapping matches are resolved by
    pattern priority (earlier in the list wins).
    """

    def __init__(self, *, enabled_types: list[EntityType] | None = None) -> None:
        self._enabled = set(enabled_types) if enabled_types else {t for t, _ in _PATTERNS}
        self._lock = threading.Lock()

        # metrics
        self._total = 0
        self._total_entities = 0
        self._by_type: dict[str, int] = {}

    def extract(self, text: str) -> EntityResult:
        doc = text or ""
        claimed: list[tuple[int, int]] = []
        found: list[Entity] = []

        for etype, pattern in _PATTERNS:
            if etype not in self._enabled:
                continue
            for m in pattern.finditer(doc):
                s, e = m.start(), m.end()
                if any(not (e <= cs or s >= ce) for cs, ce in claimed):
                    continue  # overlaps higher-priority entity
                claimed.append((s, e))
                found.append(Entity(etype.value, m.group().strip(), s, e))

        found.sort(key=lambda x: x.start)
        counts: dict[str, int] = {}
        for ent in found:
            counts[ent.type] = counts.get(ent.type, 0) + 1

        self._record(len(found), counts)
        return EntityResult(entities=found, counts_by_type=counts)

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def _record(self, n: int, by_type: dict[str, int]) -> None:
        with self._lock:
            self._total += 1
            self._total_entities += n
            for k, v in by_type.items():
                self._by_type[k] = self._by_type.get(k, 0) + v

    def metrics(self) -> dict:
        with self._lock:
            n = self._total
            return {
                "total_extractions": n,
                "total_entities": self._total_entities,
                "by_type": dict(self._by_type),
                "avg_entities": round(self._total_entities / n, 4) if n else 0.0,
                "enabled_types": sorted(t.value for t in self._enabled),
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total = 0
            self._total_entities = 0
            self._by_type = {}
