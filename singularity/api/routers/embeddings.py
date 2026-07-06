"""
Embedding endpoints (Fáze 61, v2.0). Extracted from api/main.py.

Routes and behaviour are identical to the originals.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from api.state import embedding_provider
from core.embeddings import cosine_similarity

router = APIRouter(tags=["Embeddings"])


class EmbedRequest(BaseModel):
    text: str


class SimilarityRequest(BaseModel):
    text_a: str
    text_b: str


@router.post("/embeddings")
async def embeddings_embed(req: EmbedRequest):
    """Embed text into a vector (offline feature-hashing provider by default)."""
    vec = embedding_provider.embed(req.text)
    return {"dim": embedding_provider.dim, "embedding": vec}


@router.post("/embeddings/similarity")
async def embeddings_similarity(req: SimilarityRequest):
    """Cosine similarity between two texts' embeddings."""
    a = embedding_provider.embed(req.text_a)
    b = embedding_provider.embed(req.text_b)
    return {"similarity": round(cosine_similarity(a, b), 6)}


@router.get("/embeddings/metrics")
async def embeddings_metrics():
    """Embedding provider metrics (incl. cache hit-rate when caching)."""
    return embedding_provider.metrics()
