"""
Unit tests — Typed SDK Client (Fáze 70). Fully offline.

The client is driven against the in-process app via httpx ASGITransport, so
every typed method is exercised end-to-end without a network.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport

from api.main import app
from sdk import SingularityClient, export_openapi


def _client() -> SingularityClient:
    return SingularityClient(base_url="http://sdk", transport=ASGITransport(app=app))


# ── OpenAPI export ───────────────────────────────────────────────────────────────

def test_export_openapi_shape():
    schema = export_openapi(app)
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "Singularity API"
    assert schema["info"]["version"] == "1.0.0"
    assert "/health" in schema["paths"]


def test_openapi_covers_client_endpoints():
    schema = export_openapi(app)
    paths = schema["paths"]
    for p in ("/analyze/text", "/embeddings", "/vectors/search",
              "/retrieve/search", "/rerank", "/cost/compare"):
        assert p in paths


# ── Client: health ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_client_health():
    async with _client() as c:
        h = await c.health()
    assert h["status"] == "ok"
    assert h["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_client_healthz():
    async with _client() as c:
        h = await c.healthz()
    assert h["status"] in ("healthy", "degraded")


# ── Client: NLP ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_client_analyze_text():
    async with _client() as c:
        r = await c.analyze_text("This is fantastic! Shipped on 2024-06-15.",
                                 summary=False, keywords=False)
    assert r["sentiment"]["polarity"] == "positive"
    assert any(e["type"] == "DATE" for e in r["entities"])


@pytest.mark.asyncio
async def test_client_sentiment_and_entities():
    async with _client() as c:
        s = await c.sentiment("this is terrible and broken")
        e = await c.entities("email a@b.com on 2024-01-01")
    assert s["polarity"] == "negative"
    types = {x["type"] for x in e["entities"]}
    assert "EMAIL" in types and "DATE" in types


@pytest.mark.asyncio
async def test_client_language():
    async with _client() as c:
        r = await c.detect_language("the cat is on the table and that is what we have")
    assert r["language"] == "en"


# ── Client: embeddings & vectors ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_client_embed_and_similarity():
    async with _client() as c:
        emb = await c.embed("hello world")
        sim = await c.similarity("the quick brown fox", "the quick brown cat")
    assert emb["dim"] == len(emb["embedding"])
    assert 0.0 <= sim["similarity"] <= 1.0


@pytest.mark.asyncio
async def test_client_vector_index_search():
    async with _client() as c:
        await c.vectors_index([
            {"doc_id": "a", "text": "machine learning and neural networks"},
            {"doc_id": "b", "text": "cooking pasta with tomato sauce"},
        ])
        r = await c.vectors_search("deep learning models", top_k=1)
    assert len(r["hits"]) == 1


# ── Client: RAG lexical ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_client_chunk_retrieve():
    async with _client() as c:
        chunks = await c.chunk("First sentence here. Second sentence there. Third one.",
                               chunk_size=40, overlap=0, strategy="sentence")
        assert chunks["chunk_count"] >= 2
        await c.retrieve_index([{"doc_id": "d1", "text": "the answer is 42"}])
        hits = await c.retrieve_search("what is the answer", top_k=1)
    assert "hits" in hits


@pytest.mark.asyncio
async def test_client_rerank():
    async with _client() as c:
        r = await c.rerank([[{"doc_id": "x", "score": 1.0}],
                            [{"doc_id": "x", "score": 0.9}]], method="reciprocal_rank")
    assert len(r["results"]) >= 1


# ── Client: utilities ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_client_cost_and_validate():
    async with _client() as c:
        cost = await c.cost_compare("hello world " * 20)
        val = await c.validate('{"answer": 42}',
                               [{"type": "json", "required_keys": ["answer"]}])
    assert cost["cheapest"]
    assert val["valid"] is True


@pytest.mark.asyncio
async def test_client_anonymize():
    async with _client() as c:
        r = await c.anonymize("email me at john@example.com")
    assert "[EMAIL_1]" in r["anonymized_text"]
