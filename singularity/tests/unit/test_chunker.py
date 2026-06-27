"""
Unit tests — Document Chunker (Fáze 36). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.chunker import Chunk, ChunkResult, ChunkStrategy, DocumentChunker


# ── Construction ─────────────────────────────────────────────────────────────────

def test_invalid_chunk_size_raises():
    with pytest.raises(ValueError):
        DocumentChunker(chunk_size=0)


def test_invalid_overlap_negative_raises():
    with pytest.raises(ValueError):
        DocumentChunker(overlap=-1)


def test_overlap_ge_chunk_size_raises():
    with pytest.raises(ValueError):
        DocumentChunker(chunk_size=100, overlap=100)


# ── Empty / whitespace ───────────────────────────────────────────────────────────

def test_empty_text_no_chunks():
    c = DocumentChunker()
    result = c.chunk("")
    assert result.chunk_count == 0
    assert result.chunks == []


def test_whitespace_only_no_chunks():
    c = DocumentChunker()
    result = c.chunk("   \n\n   ")
    assert result.chunk_count == 0


# ── CHARACTER strategy ───────────────────────────────────────────────────────────

def test_character_basic_split():
    c = DocumentChunker(chunk_size=10, overlap=0, strategy=ChunkStrategy.CHARACTER)
    result = c.chunk("abcdefghijklmnopqrst")  # 20 chars → 2 chunks of 10
    assert result.chunk_count == 2
    assert result.chunks[0].text == "abcdefghij"
    assert result.chunks[1].text == "klmnopqrst"


def test_character_with_overlap():
    c = DocumentChunker(chunk_size=10, overlap=3, strategy=ChunkStrategy.CHARACTER)
    result = c.chunk("abcdefghijklmnop")  # 16 chars, step=7
    # chunk0: [0:10], chunk1: [7:16]
    assert result.chunks[0].text == "abcdefghij"
    assert result.chunks[1].text == "hijklmnop"
    # overlap region present
    assert result.chunks[1].text.startswith("hij")


def test_character_shorter_than_chunk_size():
    c = DocumentChunker(chunk_size=100, overlap=10, strategy=ChunkStrategy.CHARACTER)
    result = c.chunk("short text")
    assert result.chunk_count == 1
    assert result.chunks[0].text == "short text"


def test_character_offsets():
    c = DocumentChunker(chunk_size=5, overlap=0, strategy=ChunkStrategy.CHARACTER)
    result = c.chunk("0123456789")
    assert result.chunks[0].start == 0
    assert result.chunks[0].end == 5
    assert result.chunks[1].start == 5
    assert result.chunks[1].end == 10


# ── SENTENCE strategy ────────────────────────────────────────────────────────────

def test_sentence_packs_whole_sentences():
    c = DocumentChunker(chunk_size=40, overlap=0, strategy=ChunkStrategy.SENTENCE)
    text = "First sentence. Second one. Third here."
    result = c.chunk(text)
    # each chunk should contain complete sentences (end with . ! or ?)
    for ch in result.chunks:
        assert ch.text.rstrip()[-1] in ".!?"


def test_sentence_multiple_chunks():
    c = DocumentChunker(chunk_size=20, overlap=0, strategy=ChunkStrategy.SENTENCE)
    text = "Aaa bbb ccc. Ddd eee fff. Ggg hhh iii."
    result = c.chunk(text)
    assert result.chunk_count >= 2


def test_sentence_oversized_unit_becomes_own_chunk():
    c = DocumentChunker(chunk_size=10, overlap=0, strategy=ChunkStrategy.SENTENCE)
    text = "This single sentence is way longer than ten characters."
    result = c.chunk(text)
    # not dropped — emitted as one oversized chunk
    assert result.chunk_count == 1
    assert "longer" in result.chunks[0].text


def test_sentence_single_fits():
    c = DocumentChunker(chunk_size=100, overlap=0, strategy=ChunkStrategy.SENTENCE)
    result = c.chunk("Just one sentence here.")
    assert result.chunk_count == 1


# ── PARAGRAPH strategy ───────────────────────────────────────────────────────────

def test_paragraph_split():
    c = DocumentChunker(chunk_size=50, overlap=0, strategy=ChunkStrategy.PARAGRAPH)
    text = "Para one has some text.\n\nPara two has other text.\n\nPara three."
    result = c.chunk(text)
    assert result.chunk_count >= 1
    # joined chunks should cover all paragraphs
    joined = " ".join(ch.text for ch in result.chunks)
    assert "Para one" in joined
    assert "Para three" in joined


def test_paragraph_packs_small_paragraphs():
    c = DocumentChunker(chunk_size=100, overlap=0, strategy=ChunkStrategy.PARAGRAPH)
    text = "Short a.\n\nShort b.\n\nShort c."
    result = c.chunk(text)
    # all fit in one chunk
    assert result.chunk_count == 1
    assert "Short a." in result.chunks[0].text
    assert "Short c." in result.chunks[0].text


# ── Overlap in unit packing ──────────────────────────────────────────────────────

def test_sentence_overlap_carries_tail():
    c = DocumentChunker(chunk_size=25, overlap=10, strategy=ChunkStrategy.SENTENCE)
    text = "Alpha beta gamma. Delta epsilon zeta. Eta theta iota."
    result = c.chunk(text)
    assert result.chunk_count >= 2
    # second chunk should contain some trailing context from the first
    assert len(result.chunks) >= 2


# ── Strategy override ────────────────────────────────────────────────────────────

def test_strategy_override_per_call():
    c = DocumentChunker(chunk_size=10, overlap=0, strategy=ChunkStrategy.SENTENCE)
    result = c.chunk("abcdefghijklmno", strategy=ChunkStrategy.CHARACTER)
    assert result.strategy == ChunkStrategy.CHARACTER
    assert result.chunk_count == 2


# ── Result shape ─────────────────────────────────────────────────────────────────

def test_result_to_dict_shape():
    c = DocumentChunker(chunk_size=10, overlap=0, strategy=ChunkStrategy.CHARACTER)
    result = c.chunk("abcdefghijklmnop")
    d = result.to_dict()
    for key in ("chunks", "chunk_count", "strategy", "original_length", "avg_chunk_size"):
        assert key in d
    for key in ("index", "text", "start", "end", "char_count"):
        assert key in d["chunks"][0]


def test_chunk_indices_sequential():
    c = DocumentChunker(chunk_size=5, overlap=0, strategy=ChunkStrategy.CHARACTER)
    result = c.chunk("0123456789012345")
    indices = [ch.index for ch in result.chunks]
    assert indices == list(range(len(result.chunks)))


def test_avg_chunk_size_computed():
    c = DocumentChunker(chunk_size=10, overlap=0, strategy=ChunkStrategy.CHARACTER)
    result = c.chunk("abcdefghij")  # one chunk of 10
    assert result.avg_chunk_size == 10.0


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_accumulate():
    c = DocumentChunker(chunk_size=5, overlap=0, strategy=ChunkStrategy.CHARACTER)
    c.chunk("0123456789")   # 2 chunks
    c.chunk("abcde")        # 1 chunk
    m = c.metrics()
    assert m["total_documents"] == 2
    assert m["total_chunks"] == 3
    assert m["avg_chunks_per_doc"] == 1.5


def test_metrics_empty_doc_counted():
    c = DocumentChunker()
    c.chunk("")
    m = c.metrics()
    assert m["total_documents"] == 1
    assert m["total_chunks"] == 0


def test_metrics_reset():
    c = DocumentChunker(chunk_size=5, overlap=0, strategy=ChunkStrategy.CHARACTER)
    c.chunk("0123456789")
    c.reset_metrics()
    m = c.metrics()
    assert m["total_documents"] == 0
    assert m["total_chunks"] == 0


def test_metrics_shape():
    c = DocumentChunker()
    m = c.metrics()
    for key in ("total_documents", "total_chunks", "avg_chunks_per_doc",
                "chunk_size", "overlap", "strategy"):
        assert key in m


# ── Coverage: no content lost (character, no overlap) ─────────────────────────────

def test_character_no_overlap_reconstructs():
    c = DocumentChunker(chunk_size=7, overlap=0, strategy=ChunkStrategy.CHARACTER)
    doc = "The quick brown fox jumps over the lazy dog"
    result = c.chunk(doc)
    reconstructed = "".join(ch.text for ch in result.chunks)
    assert reconstructed == doc
