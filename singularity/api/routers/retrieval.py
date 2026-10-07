"""
Retrieval / RAG endpoints. Extracted from api/main.py (maintainability refactor).

Routes and behaviour are identical to the originals.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.state import _chunker, _citation_tracker, _reranker, _retriever
from config.settings import settings
from core.chunker import ChunkStrategy, DocumentChunker
from core.citation_tracker import CitationTracker
from core.reranker import FusionMethod

router = APIRouter()

# ── Citation Tracker (Fáze 35) ──────────────────────────────────────────────────

class CitationTrackRequest(BaseModel):
    response: str
    sources: list[dict]   # [{"source_id"/"id": str, "text": str}]
    threshold: float | None = None


@router.post("/citations/track", tags=["Citations"])
async def citations_track(req: CitationTrackRequest):
    """Annotate response sentences with supporting sources; flag unsupported claims."""
    if req.threshold is not None:
        try:
            tracker = CitationTracker(
                threshold=req.threshold,
                max_citations=settings.citation_max_per_sentence,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    else:
        tracker = _citation_tracker
    return tracker.track(req.response, req.sources).to_dict()


@router.get("/citations/metrics", tags=["Citations"])
async def citations_metrics():
    """Citation tracker metrics: overall grounding score across reports."""
    return _citation_tracker.metrics()


# ── Document Chunker (Fáze 36) ──────────────────────────────────────────────────

class ChunkRequest(BaseModel):
    text: str
    chunk_size: int | None = None
    overlap: int | None = None
    strategy: str | None = None  # character | sentence | paragraph


@router.post("/chunk", tags=["Chunker"])
async def chunk_document(req: ChunkRequest):
    """Split a document into overlapping chunks for RAG ingestion."""
    if req.chunk_size is not None or req.overlap is not None:
        try:
            chunker = DocumentChunker(
                chunk_size=req.chunk_size or settings.chunk_size,
                overlap=req.overlap if req.overlap is not None else settings.chunk_overlap,
                strategy=ChunkStrategy(req.strategy or settings.chunk_strategy),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    else:
        chunker = _chunker

    strat = None
    if req.strategy is not None:
        try:
            strat = ChunkStrategy(req.strategy)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown strategy: {req.strategy!r}")

    return chunker.chunk(req.text, strategy=strat).to_dict()


@router.get("/chunk/metrics", tags=["Chunker"])
async def chunk_metrics():
    """Document chunker metrics: total docs/chunks, avg chunks per doc."""
    return _chunker.metrics()


# ── BM25 Retriever (Fáze 37) ────────────────────────────────────────────────────

class RetrieveIndexRequest(BaseModel):
    documents: list[dict]   # [{"doc_id"/"id", "text", "metadata"?}]


class RetrieveSearchRequest(BaseModel):
    query: str
    top_k: int | None = None


@router.post("/retrieve/index", tags=["Retriever"])
async def retrieve_index(req: RetrieveIndexRequest):
    """Index documents into the BM25 retriever. Returns counts."""
    added = _retriever.add_many(req.documents)
    return {"added": added, "indexed_documents": _retriever.size}


@router.post("/retrieve/search", tags=["Retriever"])
async def retrieve_search(req: RetrieveSearchRequest):
    """Search the BM25 index for the top-k most relevant documents."""
    try:
        hits = _retriever.search(req.query, top_k=req.top_k or settings.retriever_top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"query": req.query, "hits": [h.to_dict() for h in hits]}


@router.delete("/retrieve", tags=["Retriever"])
async def retrieve_clear():
    """Clear the BM25 index. Returns number of documents removed."""
    return {"removed": _retriever.clear()}


@router.get("/retrieve/metrics", tags=["Retriever"])
async def retrieve_metrics():
    """BM25 retriever metrics: index size, vocabulary, search counts."""
    return _retriever.metrics()


# ── Hybrid Reranker (Fáze 38) ───────────────────────────────────────────────────

class RerankRequest(BaseModel):
    ranked_lists: list[list[dict]]   # each list: [{doc_id/id, score?, text?, metadata?}]
    method: str | None = None        # reciprocal_rank | weighted_score
    weights: list[float] | None = None
    top_k: int | None = None


@router.post("/rerank", tags=["Reranker"])
async def rerank(req: RerankRequest):
    """Fuse multiple ranked result lists into one consensus ranking."""
    method = None
    if req.method is not None:
        try:
            method = FusionMethod(req.method)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown method: {req.method!r}")
    try:
        fused = _reranker.fuse(
            req.ranked_lists,
            method=method,
            weights=req.weights,
            top_k=req.top_k,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"results": [f.to_dict() for f in fused]}


@router.get("/rerank/metrics", tags=["Reranker"])
async def rerank_metrics():
    """Hybrid reranker metrics: fusion counts, average output size."""
    return _reranker.metrics()
