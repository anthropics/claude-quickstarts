"""
Singularity — Token Streaming (Fáze 64, v2.0 #4).

End-to-end token streaming helpers. LLM providers can emit tokens as they are
generated; this module turns an async token iterator into Server-Sent-Events
frames, accumulates the full text, tracks token counts, and flushes on
sentence boundaries so a UI can render coherent chunks rather than raw
fragments.

Provider-agnostic: the token source is any ``AsyncIterator[str]`` (a real
provider's ``astream`` in production, a mock async generator in tests), so the
whole pipeline is exercised offline and deterministically.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from typing import AsyncIterator


_SENTENCE_END = re.compile(r"[.!?]\s")


def sse_frame(data: dict, *, event: str | None = None) -> str:
    """Format a Server-Sent-Events frame (terminated by a blank line)."""
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {json.dumps(data)}\n\n"


# ── Accumulator ─────────────────────────────────────────────────────────────────

@dataclass
class StreamAccumulator:
    """Accumulates streamed token chunks and emits completed sentences."""

    text: str = ""
    _pending: str = ""
    token_count: int = 0
    sentences: list[str] = field(default_factory=list)

    def add(self, chunk: str) -> list[str]:
        """Add a chunk; return any newly completed sentences (in order)."""
        if not chunk:
            return []
        self.token_count += 1
        self.text += chunk
        self._pending += chunk
        completed: list[str] = []
        # flush every time a sentence terminator + following space appears
        while True:
            m = _SENTENCE_END.search(self._pending)
            if not m:
                break
            end = m.end() - 1  # keep the terminator, drop the trailing space split
            sentence = self._pending[:end].strip()
            self._pending = self._pending[m.end():]
            if sentence:
                completed.append(sentence)
                self.sentences.append(sentence)
        return completed

    def flush(self) -> str | None:
        """Return the trailing partial sentence (if any) and clear it."""
        rest = self._pending.strip()
        self._pending = ""
        if rest:
            self.sentences.append(rest)
            return rest
        return None


# ── Streaming metrics ────────────────────────────────────────────────────────────

class StreamMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._streams = 0
        self._tokens = 0

    def record(self, tokens: int) -> None:
        with self._lock:
            self._streams += 1
            self._tokens += tokens

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "streams": self._streams,
                "total_tokens": self._tokens,
                "avg_tokens_per_stream": round(self._tokens / self._streams, 4)
                if self._streams else 0.0,
            }

    def reset(self) -> None:
        with self._lock:
            self._streams = 0
            self._tokens = 0


# ── SSE stream generator ─────────────────────────────────────────────────────────

async def stream_sse(
    tokens: AsyncIterator[str],
    *,
    metrics: StreamMetrics | None = None,
    by_sentence: bool = False,
) -> AsyncIterator[str]:
    """
    Consume a token iterator and yield SSE frames.

    Emits one ``token`` frame per token (or one ``sentence`` frame per
    completed sentence when ``by_sentence``), then a final ``done`` frame with
    the full text and token count.
    """
    acc = StreamAccumulator()
    async for chunk in tokens:
        completed = acc.add(chunk)
        if by_sentence:
            for s in completed:
                yield sse_frame({"sentence": s}, event="sentence")
        else:
            if chunk:
                yield sse_frame({"token": chunk, "index": acc.token_count - 1},
                                event="token")
    if by_sentence:
        tail = acc.flush()
        if tail:
            yield sse_frame({"sentence": tail}, event="sentence")
    if metrics is not None:
        metrics.record(acc.token_count)
    yield sse_frame(
        {"text": acc.text, "tokens": acc.token_count,
         "sentences": len(acc.sentences)},
        event="done",
    )


async def collect_tokens(tokens: AsyncIterator[str]) -> str:
    """Non-streaming convenience: accumulate a token iterator into full text."""
    acc = StreamAccumulator()
    async for chunk in tokens:
        acc.add(chunk)
    acc.flush()
    return acc.text
