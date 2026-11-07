"""
Singularity — Document Chunker (Fáze 36).

Splits long documents into overlapping chunks for RAG ingestion. Three
boundary strategies trade off chunk-size precision against semantic
coherence:

  - CHARACTER:  hard slice by character count (most precise size, may cut
                mid-word/sentence)
  - SENTENCE:   pack whole sentences up to the size budget (keeps sentences
                intact)
  - PARAGRAPH:  pack whole paragraphs up to the size budget (keeps
                paragraphs intact)

Overlap (in characters) is carried from the tail of one chunk into the head
of the next to preserve context across boundaries. Dependency-free and
deterministic for offline tests.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from enum import Enum


# ── Strategy ────────────────────────────────────────────────────────────────────

class ChunkStrategy(str, Enum):
    CHARACTER = "character"
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")


# ── Data structures ─────────────────────────────────────────────────────────────

@dataclass
class Chunk:
    index: int
    text: str
    start: int           # char offset in original document (approx for packed)
    end: int
    char_count: int

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "char_count": self.char_count,
        }


@dataclass
class ChunkResult:
    chunks: list[Chunk] = field(default_factory=list)
    chunk_count: int = 0
    strategy: ChunkStrategy = ChunkStrategy.CHARACTER
    original_length: int = 0
    avg_chunk_size: float = 0.0

    def to_dict(self) -> dict:
        return {
            "chunks": [c.to_dict() for c in self.chunks],
            "chunk_count": self.chunk_count,
            "strategy": self.strategy.value,
            "original_length": self.original_length,
            "avg_chunk_size": self.avg_chunk_size,
        }


# ── Chunker ─────────────────────────────────────────────────────────────────────

class DocumentChunker:
    """
    Split documents into overlapping chunks.

    ``chunk_size`` is the target size in characters. ``overlap`` is the number
    of trailing characters re-included at the start of the next chunk (must be
    < chunk_size). For SENTENCE / PARAGRAPH, a unit that alone exceeds
    chunk_size becomes its own (oversized) chunk rather than being dropped.
    """

    def __init__(
        self,
        *,
        chunk_size: int = 1000,
        overlap: int = 100,
        strategy: ChunkStrategy = ChunkStrategy.SENTENCE,
    ) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be >= 1")
        if overlap < 0:
            raise ValueError("overlap must be >= 0")
        if overlap >= chunk_size:
            raise ValueError("overlap must be < chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.strategy = strategy
        self._lock = threading.Lock()

        # metrics
        self._total_docs = 0
        self._total_chunks = 0

    # ── Public API ──────────────────────────────────────────────────────────────

    def chunk(self, text: str, strategy: ChunkStrategy | None = None) -> ChunkResult:
        strat = strategy or self.strategy
        doc = text or ""

        if not doc.strip():
            self._record(0)
            return ChunkResult(chunks=[], chunk_count=0, strategy=strat,
                               original_length=len(doc), avg_chunk_size=0.0)

        if strat == ChunkStrategy.CHARACTER:
            raw = self._chunk_character(doc)
        elif strat == ChunkStrategy.PARAGRAPH:
            raw = self._chunk_units(doc, _PARAGRAPH_SPLIT.split(doc), joiner="\n\n")
        else:  # SENTENCE
            raw = self._chunk_units(doc, _SENTENCE_SPLIT.split(doc), joiner=" ")

        chunks = [
            Chunk(index=i, text=t, start=s, end=e, char_count=len(t))
            for i, (t, s, e) in enumerate(raw)
        ]
        total_chars = sum(c.char_count for c in chunks)
        avg = round(total_chars / len(chunks), 2) if chunks else 0.0
        self._record(len(chunks))

        return ChunkResult(
            chunks=chunks,
            chunk_count=len(chunks),
            strategy=strat,
            original_length=len(doc),
            avg_chunk_size=avg,
        )

    # ── Strategy implementations ──────────────────────────────────────────────────

    def _chunk_character(self, doc: str) -> list[tuple[str, int, int]]:
        chunks: list[tuple[str, int, int]] = []
        step = self.chunk_size - self.overlap
        pos = 0
        n = len(doc)
        while pos < n:
            end = min(pos + self.chunk_size, n)
            chunks.append((doc[pos:end], pos, end))
            if end >= n:
                break
            pos += step
        return chunks

    def _chunk_units(
        self, doc: str, units: list[str], *, joiner: str
    ) -> list[tuple[str, int, int]]:
        units = [u.strip() for u in units if u.strip()]
        chunks: list[tuple[str, int, int]] = []

        current = ""
        cursor = 0  # approximate running char offset into doc

        def _emit(buf: str, start: int) -> None:
            chunks.append((buf, start, start + len(buf)))

        chunk_start = 0
        for unit in units:
            if not current:
                current = unit
                chunk_start = cursor
            elif len(current) + len(joiner) + len(unit) <= self.chunk_size:
                current = current + joiner + unit
            else:
                _emit(current, chunk_start)
                # carry overlap tail into the next chunk
                tail = current[-self.overlap:] if self.overlap else ""
                cursor += len(current) + len(joiner)
                if tail:
                    current = tail + joiner + unit
                    chunk_start = max(0, cursor - len(tail) - len(joiner))
                else:
                    current = unit
                    chunk_start = cursor
        if current:
            _emit(current, chunk_start)
        return chunks

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def _record(self, n_chunks: int) -> None:
        with self._lock:
            self._total_docs += 1
            self._total_chunks += n_chunks

    def metrics(self) -> dict:
        with self._lock:
            docs = self._total_docs
            return {
                "total_documents": docs,
                "total_chunks": self._total_chunks,
                "avg_chunks_per_doc": round(self._total_chunks / docs, 2)
                if docs else 0.0,
                "chunk_size": self.chunk_size,
                "overlap": self.overlap,
                "strategy": self.strategy.value,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total_docs = 0
            self._total_chunks = 0
