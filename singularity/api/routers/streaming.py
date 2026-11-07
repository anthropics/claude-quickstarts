"""
Token Streaming endpoints (Fáze 64, v2.0 #4). Extracted from api/main.py.

Routes and behaviour are identical to the originals.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.state import stream_metrics
from core.streaming import stream_sse

router = APIRouter(tags=["Streaming"])


class TokenStreamRequest(BaseModel):
    text: str
    by_sentence: bool = False


@router.post("/stream/tokens")
async def stream_tokens(req: TokenStreamRequest):
    """Stream text back token-by-token as SSE.

    Demonstrates the end-to-end token-streaming path with a whitespace
    tokenizer as the source; in production the source is a provider's
    ``astream``. Emits ``token`` (or ``sentence``) frames then a ``done`` frame.
    """
    async def _source():
        for i, word in enumerate((req.text or "").split()):
            yield (word if i == 0 else " " + word)

    return StreamingResponse(
        stream_sse(_source(), metrics=stream_metrics, by_sentence=req.by_sentence),
        media_type="text/event-stream",
    )


@router.get("/stream/metrics")
async def stream_metrics_endpoint():
    """Token streaming metrics: stream count, tokens, avg per stream."""
    return stream_metrics.snapshot()
