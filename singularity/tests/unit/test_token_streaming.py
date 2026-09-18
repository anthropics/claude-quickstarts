"""
Unit tests — Token Streaming (Fáze 64). Fully offline (mock token iterators).
"""

from __future__ import annotations

import json
import pytest

from core.streaming import (
    StreamAccumulator,
    StreamMetrics,
    collect_tokens,
    sse_frame,
    stream_sse,
)


async def _agen(tokens):
    for t in tokens:
        yield t


def _parse(frame: str) -> dict:
    for line in frame.splitlines():
        if line.startswith("data: "):
            return json.loads(line[len("data: "):])
    raise AssertionError("no data line")


# ── sse_frame ────────────────────────────────────────────────────────────────────

def test_sse_frame_basic():
    f = sse_frame({"a": 1})
    assert f == 'data: {"a": 1}\n\n'


def test_sse_frame_with_event():
    f = sse_frame({"a": 1}, event="token")
    assert f.startswith("event: token\n")
    assert f.endswith("\n\n")


# ── StreamAccumulator ────────────────────────────────────────────────────────────

def test_accumulator_builds_text():
    acc = StreamAccumulator()
    acc.add("Hello")
    acc.add(" world")
    assert acc.text == "Hello world"
    assert acc.token_count == 2


def test_accumulator_empty_chunk_ignored():
    acc = StreamAccumulator()
    assert acc.add("") == []
    assert acc.token_count == 0


def test_accumulator_completes_sentence():
    acc = StreamAccumulator()
    out = []
    for tok in ["The ", "cat ", "sat. ", "Then ", "left."]:
        out += acc.add(tok)
    assert "The cat sat." in out
    assert acc.flush() == "Then left."


def test_accumulator_multiple_sentences_one_chunk():
    acc = StreamAccumulator()
    out = acc.add("One. Two. Three ")
    assert out == ["One.", "Two."]


def test_accumulator_flush_none_when_empty():
    acc = StreamAccumulator()
    acc.add("Done. ")
    assert acc.flush() is None


def test_accumulator_sentences_tracked():
    acc = StreamAccumulator()
    acc.add("A. B. ")
    acc.flush()
    assert acc.sentences == ["A.", "B."]


# ── stream_sse (token mode) ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stream_sse_token_frames():
    frames = [f async for f in stream_sse(_agen(["a", "b", "c"]))]
    assert len(frames) == 4  # 3 token + 1 done
    assert "event: token" in frames[0]
    assert "event: done" in frames[-1]


@pytest.mark.asyncio
async def test_stream_sse_done_has_full_text():
    frames = [f async for f in stream_sse(_agen(["Hel", "lo!"]))]
    done = _parse(frames[-1])
    assert done["text"] == "Hello!"
    assert done["tokens"] == 2


@pytest.mark.asyncio
async def test_stream_sse_token_indices():
    frames = [f async for f in stream_sse(_agen(["x", "y"]))]
    assert _parse(frames[0])["index"] == 0
    assert _parse(frames[1])["index"] == 1


@pytest.mark.asyncio
async def test_stream_sse_empty_iterator():
    frames = [f async for f in stream_sse(_agen([]))]
    assert len(frames) == 1
    done = _parse(frames[0])
    assert done["text"] == ""
    assert done["tokens"] == 0


# ── stream_sse (sentence mode) ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stream_sse_by_sentence():
    toks = ["The ", "cat ", "sat. ", "It ", "purred."]
    frames = [f async for f in stream_sse(_agen(toks), by_sentence=True)]
    events = [f for f in frames if "event: sentence" in f]
    sentences = [_parse(f)["sentence"] for f in events]
    assert "The cat sat." in sentences
    assert "It purred." in sentences  # via flush


# ── metrics ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stream_metrics_recorded():
    m = StreamMetrics()
    _ = [f async for f in stream_sse(_agen(["a", "b", "c"]), metrics=m)]
    snap = m.snapshot()
    assert snap["streams"] == 1
    assert snap["total_tokens"] == 3
    assert snap["avg_tokens_per_stream"] == 3.0


def test_stream_metrics_reset():
    m = StreamMetrics()
    m.record(5)
    m.reset()
    assert m.snapshot()["streams"] == 0


def test_stream_metrics_shape():
    m = StreamMetrics()
    snap = m.snapshot()
    for key in ("streams", "total_tokens", "avg_tokens_per_stream"):
        assert key in snap


# ── collect_tokens ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collect_tokens():
    text = await collect_tokens(_agen(["Hello", " ", "there."]))
    assert text == "Hello there."
