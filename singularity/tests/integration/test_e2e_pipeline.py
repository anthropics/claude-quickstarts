"""
End-to-End Integration Suite (Fáze 59).

Drives the fully-wired FastAPI app (api.main) through ASGITransport — no real
network, no API keys — exercising the deterministic pipelines end to end:

  - RAG:           /chunk → /retrieve/index → /retrieve/search → /rerank
  - NLP:           /analyze/text, /sentiment, /entities, /keywords, /summarize,
                   /language/detect, /readability, /parse/json
  - Privacy:       /anonymize → /anonymize/restore round-trip
  - Observability: /percentile, /anomaly, /slo, /healthz
  - Control plane: /flags, /webhooks, /dedup, /fuzzy/match

These tests verify the modules are correctly registered and composed in the
running application, complementing the per-module unit tests.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from api.main import app

pytestmark = pytest.mark.integration


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://e2e")


# ── RAG pipeline: chunk → index → search → rerank ────────────────────────────────

@pytest.mark.asyncio
async def test_rag_pipeline_end_to_end():
    doc = (
        "Photosynthesis converts sunlight into chemical energy in plants. "
        "Chlorophyll absorbs light in the blue and red wavelengths. "
        "The Calvin cycle fixes carbon dioxide into glucose. "
        "Cellular respiration then releases that stored energy."
    )
    async with await _client() as c:
        # 1. chunk the document
        r = await c.post("/chunk", json={"text": doc, "chunk_size": 80,
                                         "overlap": 0, "strategy": "sentence"})
        assert r.status_code == 200
        chunks = r.json()["chunks"]
        assert len(chunks) >= 2

        # 2. index the chunks
        docs = [{"doc_id": f"c{ch['index']}", "text": ch["text"]} for ch in chunks]
        r = await c.post("/retrieve/index", json={"documents": docs})
        assert r.status_code == 200
        assert r.json()["added"] == len(docs)

        # 3. search
        r = await c.post("/retrieve/search",
                         json={"query": "how do plants capture light", "top_k": 3})
        assert r.status_code == 200
        hits = r.json()["hits"]
        assert len(hits) >= 1

        # 4. rerank two ranked lists (lexical + a stand-in semantic order)
        lexical = [{"doc_id": h["doc_id"], "score": h["score"]} for h in hits]
        semantic = list(reversed(lexical))
        r = await c.post("/rerank", json={"ranked_lists": [lexical, semantic],
                                          "method": "reciprocal_rank"})
        assert r.status_code == 200
        assert len(r.json()["results"]) >= 1


# ── NLP: composed analysis + individual analyzers ────────────────────────────────

@pytest.mark.asyncio
async def test_text_analytics_composed():
    text = ("The new release is absolutely fantastic and I love the speed. "
            "It shipped on 2024-06-15 and costs $20 per month.")
    async with await _client() as c:
        r = await c.post("/analyze/text", json={"text": text})
        assert r.status_code == 200
        body = r.json()
        assert body["sentiment"]["polarity"] == "positive"
        assert body["language"]["language"] == "en"
        assert "p50" not in body  # sanity: not a percentile report
        assert any(e["type"] == "DATE" for e in body["entities"])
        assert any(e["type"] == "MONEY" for e in body["entities"])
        assert "readability" in body
        assert "summary" in body


@pytest.mark.asyncio
async def test_individual_nlp_endpoints():
    async with await _client() as c:
        r = await c.post("/sentiment", json={"text": "This is terrible and broken."})
        assert r.json()["polarity"] == "negative"

        r = await c.post("/entities", json={"text": "Email a@b.com on 2024-01-01."})
        types = {e["type"] for e in r.json()["entities"]}
        assert "EMAIL" in types and "DATE" in types

        r = await c.post("/keywords", json={"text": "machine learning models and neural networks", "top_k": 3})
        assert len(r.json()["keywords"]) >= 1

        r = await c.post("/language/detect", json={"text": "the cat is on the table here"})
        assert r.json()["language"] == "en"

        r = await c.post("/parse/json", json={"text": "result: ```json\n{\"ok\": true}\n```"})
        assert r.json()["success"] is True
        assert r.json()["data"] == {"ok": True}


# ── Privacy: anonymize → restore round-trip ──────────────────────────────────────

@pytest.mark.asyncio
async def test_anonymize_restore_round_trip():
    original = "Contact john@example.com or call 555-123-4567 today."
    async with await _client() as c:
        r = await c.post("/anonymize", json={"text": original})
        body = r.json()
        assert "[EMAIL_1]" in body["anonymized_text"]
        assert "john@example.com" not in body["anonymized_text"]

        r = await c.post("/anonymize/restore",
                         json={"text": body["anonymized_text"], "mapping": body["mapping"]})
        assert r.json()["restored_text"] == original


# ── Observability: percentile + anomaly + SLO ────────────────────────────────────

@pytest.mark.asyncio
async def test_observability_pipeline():
    async with await _client() as c:
        # percentile tracker
        for v in [10, 12, 11, 13, 10, 50, 12, 11]:
            await c.post("/percentile/observe", json={"metric": "e2e_lat", "value": v})
        r = await c.get("/percentile/summary", params={"metric": "e2e_lat"})
        assert r.status_code == 200
        assert "p99" in r.json()["percentiles"]

        # anomaly detector warms up then flags a spike
        for _ in range(8):
            await c.post("/anomaly/observe", json={"metric": "e2e_err", "value": 1.0})
        r = await c.post("/anomaly/observe", json={"metric": "e2e_err", "value": 9999.0})
        assert r.json()["is_anomaly"] is True

        # SLO: register, breach, report
        await c.post("/slo", json={"name": "e2e_api", "target": 0.99, "window": 10})
        for _ in range(10):
            await c.post("/slo/e2e_api/record", json={"outcome": "failure"})
        r = await c.get("/slo/e2e_api")
        assert r.json()["status"] == "breached"


# ── Health aggregation ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_healthz_aggregates():
    async with await _client() as c:
        r = await c.get("/healthz")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] in ("healthy", "degraded")
        names = {comp["name"] for comp in body["components"]}
        assert "task_queue" in names


# ── Control plane: feature flags ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_feature_flags_lifecycle():
    async with await _client() as c:
        r = await c.post("/flags", json={"name": "e2e_flag", "enabled": True, "rollout": 100})
        assert r.status_code == 200
        r = await c.post("/flags/e2e_flag/evaluate", params={"user": "alice"})
        assert r.json()["enabled"] is True
        # force a user off
        await c.patch("/flags/e2e_flag", json={"override_user": "bob", "override_state": False})
        r = await c.post("/flags/e2e_flag/evaluate", params={"user": "bob"})
        assert r.json()["enabled"] is False
        await c.delete("/flags/e2e_flag")


# ── Control plane: webhooks (no real network) ────────────────────────────────────

@pytest.mark.asyncio
async def test_webhooks_subscribe_and_filtered_dispatch():
    async with await _client() as c:
        r = await c.post("/webhooks/subscribe",
                         json={"url": "https://example.com/hook", "secret": "s",
                               "events": ["order.paid"]})
        assert r.status_code == 200
        sid = r.json()["sub_id"]
        # dispatch an event the subscriber does NOT listen for → no delivery, no network
        r = await c.post("/webhooks/dispatch",
                         json={"event_type": "order.refunded", "data": {}})
        assert r.json()["status"] == "no_subscribers"
        await c.delete(f"/webhooks/{sid}")


# ── Dedup + fuzzy match ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dedup_and_fuzzy():
    async with await _client() as c:
        r = await c.post("/dedup/batch", json={"texts": [
            "the quick brown fox", "the quick brown fox", "completely different text"]})
        assert r.json()["unique_count"] == 2

        r = await c.post("/fuzzy/match",
                         json={"query": "appel", "candidates": ["apple", "banana"], "top_k": 1})
        assert r.json()["best"]["candidate"] == "apple"


# ── Cross-cutting: cost estimation + validation ──────────────────────────────────

@pytest.mark.asyncio
async def test_cost_and_validation():
    async with await _client() as c:
        r = await c.post("/cost/compare", json={"prompt": "hello world " * 50})
        body = r.json()
        assert body["cheapest"]
        assert len(body["estimates"]) >= 2

        r = await c.post("/validate", json={
            "text": '{"answer": 42}',
            "constraints": [{"type": "json", "required_keys": ["answer"]}],
        })
        assert r.json()["valid"] is True
