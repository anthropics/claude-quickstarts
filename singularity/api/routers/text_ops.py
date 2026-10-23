"""
Text operations (anonymize, compare, dedup, fuzzy match) endpoints. Extracted from api/main.py (maintainability refactor).

Routes and behaviour are identical to the originals.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.state import _anonymizer, _comparator, _deduplicator, _fuzzy_matcher
from core.anonymizer import PIIAnonymizer

router = APIRouter()

# ── PII Anonymizer (Fáze 39) ────────────────────────────────────────────────────

class AnonymizeRequest(BaseModel):
    text: str


class RestoreRequest(BaseModel):
    text: str
    mapping: dict[str, str]


@router.post("/anonymize", tags=["Anonymizer"])
async def anonymize_text(req: AnonymizeRequest):
    """Reversibly replace PII with stable placeholders; returns text + mapping."""
    return _anonymizer.anonymize(req.text).to_dict()


@router.post("/anonymize/detect", tags=["Anonymizer"])
async def anonymize_detect(req: AnonymizeRequest):
    """Detect PII entities without modifying the text."""
    return {"entities": _anonymizer.detect(req.text)}


@router.post("/anonymize/restore", tags=["Anonymizer"])
async def anonymize_restore(req: RestoreRequest):
    """Re-insert original values from a placeholder mapping."""
    return {"restored_text": PIIAnonymizer.restore(req.text, req.mapping)}


@router.get("/anonymize/metrics", tags=["Anonymizer"])
async def anonymize_metrics():
    """PII anonymizer metrics: entity counts by type."""
    return _anonymizer.metrics()


# ── Response Comparator (Fáze 41) ───────────────────────────────────────────────

class CompareResponsesRequest(BaseModel):
    text_a: str
    text_b: str


@router.post("/compare/responses", tags=["Comparator"])
async def compare_responses(req: CompareResponsesRequest):
    """Sentence-level diff between two responses with similarity scores."""
    return _comparator.compare(req.text_a, req.text_b).to_dict()


@router.get("/compare/responses/metrics", tags=["Comparator"])
async def compare_responses_metrics():
    """Response comparator metrics: avg similarity, identical rate."""
    return _comparator.metrics()


# ── Deduplicator (Fáze 48) ──────────────────────────────────────────────────────

class DedupCheckRequest(BaseModel):
    text: str
    add: bool = True   # register the text if not a duplicate


class DedupBatchRequest(BaseModel):
    texts: list[str]


@router.post("/dedup/check", tags=["Dedup"])
async def dedup_check(req: DedupCheckRequest):
    """Check a text for exact/near duplicates; optionally register it."""
    if req.add:
        entry_id, check = _deduplicator.add(req.text)
        return {"entry_id": entry_id, **check.to_dict()}
    return _deduplicator.check(req.text).to_dict()


@router.post("/dedup/batch", tags=["Dedup"])
async def dedup_batch(req: DedupBatchRequest):
    """Deduplicate a list of texts, keeping first occurrences."""
    return _deduplicator.deduplicate(req.texts)


@router.delete("/dedup", tags=["Dedup"])
async def dedup_clear():
    """Clear the deduplication index."""
    return {"removed": _deduplicator.clear()}


@router.get("/dedup/metrics", tags=["Dedup"])
async def dedup_metrics():
    """Deduplicator metrics: exact/near counts, duplicate rate."""
    return _deduplicator.metrics()


# ── Fuzzy Matcher (Fáze 51) ─────────────────────────────────────────────────────

class FuzzyMatchRequest(BaseModel):
    query: str
    candidates: list[str]
    top_k: int = 5


@router.post("/fuzzy/match", tags=["Fuzzy"])
async def fuzzy_match(req: FuzzyMatchRequest):
    """Fuzzy-match a query against candidates via Levenshtein similarity."""
    try:
        result = _fuzzy_matcher.match(req.query, req.candidates, top_k=req.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result.to_dict()


@router.get("/fuzzy/metrics", tags=["Fuzzy"])
async def fuzzy_metrics():
    """Fuzzy matcher metrics: hit rate across queries."""
    return _fuzzy_matcher.metrics()
