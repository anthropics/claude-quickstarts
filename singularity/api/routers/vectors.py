"""
Vector store / dense retriever endpoints (Fáze 69, v2.0 #9).

Extracted from api/main.py into an APIRouter as part of the maintainability
refactor. Routes and behaviour are identical to the originals.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.state import vector_store

router = APIRouter(tags=["Vectors"])


class VectorIndexRequest(BaseModel):
    documents: list[dict]   # [{doc_id/id, text, metadata?}]


class VectorSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    min_score: float = 0.0


@router.post("/vectors/index")
async def vectors_index(req: VectorIndexRequest):
    """Index documents into the dense vector store (embedded on ingest)."""
    added = vector_store.add_many(req.documents)
    return {"added": added, "indexed": vector_store.size}


@router.post("/vectors/search")
async def vectors_search(req: VectorSearchRequest):
    """Semantic cosine k-NN search over the vector store."""
    try:
        hits = vector_store.search(req.query, top_k=req.top_k, min_score=req.min_score)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"query": req.query, "hits": [h.to_dict() for h in hits]}


@router.delete("/vectors")
async def vectors_clear():
    """Clear the vector index."""
    return {"removed": vector_store.clear()}


@router.get("/vectors/metrics")
async def vectors_metrics():
    """Vector store metrics: index size, dim, search counts."""
    return vector_store.metrics()
