"""
Singularity — Deduplicator (Fáze 48).

Detects exact and near-duplicate texts. Each text is reduced to a 64-bit
SimHash fingerprint over its token shingles; two texts are near-duplicates
when the Hamming distance between their fingerprints is <= a threshold.
Exact duplicates are caught first via a content hash.

Use cases: collapsing near-identical retrieval hits, dropping repeated batch
inputs, or cache-key fuzzing. Dependency-free and deterministic — pure
Python hashing, no models.
"""

from __future__ import annotations

import hashlib
import re
import threading
from dataclasses import dataclass, field


_WORD = re.compile(r"[a-z0-9]+")
_HASH_BITS = 64
_MASK = (1 << _HASH_BITS) - 1


def _tokens(text: str) -> list[str]:
    return _WORD.findall((text or "").lower())


def _shingles(tokens: list[str], k: int) -> list[str]:
    if k <= 1 or len(tokens) < k:
        return tokens or []
    return [" ".join(tokens[i:i + k]) for i in range(len(tokens) - k + 1)]


def _hash64(s: str) -> int:
    digest = hashlib.blake2b(s.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big")


def simhash(text: str, *, shingle_k: int = 2) -> int:
    """Compute a 64-bit SimHash fingerprint of a text."""
    tokens = _tokens(text)
    feats = _shingles(tokens, shingle_k)
    if not feats:
        return 0
    # Weighted bit vote.
    v = [0] * _HASH_BITS
    for feat in feats:
        h = _hash64(feat)
        for b in range(_HASH_BITS):
            if (h >> b) & 1:
                v[b] += 1
            else:
                v[b] -= 1
    out = 0
    for b in range(_HASH_BITS):
        if v[b] > 0:
            out |= (1 << b)
    return out & _MASK


def hamming(a: int, b: int) -> int:
    """Hamming distance between two 64-bit ints."""
    return bin((a ^ b) & _MASK).count("1")


def _content_hash(text: str) -> str:
    # normalized exact-dup key (whitespace/case-insensitive)
    norm = " ".join(_tokens(text))
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


# ── Result ──────────────────────────────────────────────────────────────────────

@dataclass
class DuplicateCheck:
    is_duplicate: bool
    duplicate_type: str          # "exact" | "near" | "none"
    matched_id: str | None = None
    distance: int | None = None

    def to_dict(self) -> dict:
        return {
            "is_duplicate": self.is_duplicate,
            "duplicate_type": self.duplicate_type,
            "matched_id": self.matched_id,
            "distance": self.distance,
        }


@dataclass
class _Entry:
    entry_id: str
    fingerprint: int
    content_hash: str


# ── Deduplicator ────────────────────────────────────────────────────────────────

class Deduplicator:
    """
    Maintains a set of seen fingerprints and reports duplicates.

    ``threshold`` is the max Hamming distance for a near-duplicate (0–64);
    ``shingle_k`` is the token n-gram size for SimHash features.
    """

    def __init__(self, *, threshold: int = 3, shingle_k: int = 2) -> None:
        if not 0 <= threshold <= _HASH_BITS:
            raise ValueError(f"threshold must be in [0, {_HASH_BITS}]")
        if shingle_k < 1:
            raise ValueError("shingle_k must be >= 1")
        self.threshold = threshold
        self.shingle_k = shingle_k
        self._lock = threading.Lock()

        self._entries: list[_Entry] = []
        self._by_content: dict[str, str] = {}   # content_hash → entry_id

        # metrics
        self._total_checks = 0
        self._exact = 0
        self._near = 0
        self._unique = 0

    # ── Core ──────────────────────────────────────────────────────────────────────

    def check(self, text: str) -> DuplicateCheck:
        """Check without adding."""
        chash = _content_hash(text)
        fp = simhash(text, shingle_k=self.shingle_k)
        with self._lock:
            return self._check_locked(chash, fp)

    def add(self, text: str, entry_id: str | None = None) -> tuple[str, DuplicateCheck]:
        """
        Check then register the text. Returns (entry_id, check). If it's a
        duplicate, the existing entry_id is returned and nothing new is stored.
        """
        chash = _content_hash(text)
        fp = simhash(text, shingle_k=self.shingle_k)
        with self._lock:
            result = self._check_locked(chash, fp)
            self._total_checks += 1
            if result.is_duplicate:
                if result.duplicate_type == "exact":
                    self._exact += 1
                else:
                    self._near += 1
                return result.matched_id, result
            new_id = entry_id or f"dedup{len(self._entries)}"
            self._entries.append(_Entry(new_id, fp, chash))
            self._by_content[chash] = new_id
            self._unique += 1
            return new_id, result

    def _check_locked(self, chash: str, fp: int) -> DuplicateCheck:
        # exact first
        exact_id = self._by_content.get(chash)
        if exact_id is not None:
            return DuplicateCheck(True, "exact", matched_id=exact_id, distance=0)
        # near via SimHash Hamming
        best_id = None
        best_dist = None
        for e in self._entries:
            d = hamming(fp, e.fingerprint)
            if d <= self.threshold and (best_dist is None or d < best_dist):
                best_dist = d
                best_id = e.entry_id
        if best_id is not None:
            return DuplicateCheck(True, "near", matched_id=best_id, distance=best_dist)
        return DuplicateCheck(False, "none")

    def deduplicate(self, texts: list[str]) -> dict:
        """
        Run a list through, keeping only the first occurrence of each
        unique/near-unique text. Returns kept items + duplicate mapping.
        """
        kept: list[dict] = []
        duplicates: list[dict] = []
        for i, text in enumerate(texts):
            entry_id, result = self.add(text, entry_id=f"item{i}")
            if result.is_duplicate:
                duplicates.append({
                    "index": i, "matched_id": result.matched_id,
                    "type": result.duplicate_type, "distance": result.distance,
                })
            else:
                kept.append({"index": i, "entry_id": entry_id, "text": text})
        return {
            "kept": kept,
            "duplicates": duplicates,
            "input_count": len(texts),
            "unique_count": len(kept),
            "duplicate_count": len(duplicates),
        }

    def clear(self) -> int:
        with self._lock:
            n = len(self._entries)
            self._entries.clear()
            self._by_content.clear()
            return n

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._entries)

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def metrics(self) -> dict:
        with self._lock:
            n = self._total_checks
            return {
                "total_checks": n,
                "exact_duplicates": self._exact,
                "near_duplicates": self._near,
                "unique": self._unique,
                "dup_rate": round((self._exact + self._near) / n, 4) if n else 0.0,
                "indexed": len(self._entries),
                "threshold": self.threshold,
                "shingle_k": self.shingle_k,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total_checks = 0
            self._exact = 0
            self._near = 0
            self._unique = 0
