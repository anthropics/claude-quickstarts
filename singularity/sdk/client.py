"""
Singularity — Typed SDK Client (Fáze 70, v2.0 #10).

A thin, typed async wrapper over the Singularity HTTP API so consumers get
IDE completion and a stable contract instead of hand-rolling ~190 raw HTTP
calls. Every method maps to one endpoint and returns the parsed JSON.

The client accepts an injectable httpx ``transport`` — pass an
``ASGITransport(app=app)`` to drive the in-process app in tests (no network),
or omit it to talk to a running server over ``base_url``.

Also exports the OpenAPI schema (``export_openapi``) so a fully-generated
client in any language can be produced with standard tooling.
"""

from __future__ import annotations

from typing import Any

import httpx


def export_openapi(app: Any) -> dict:
    """Return the app's OpenAPI schema (feed to openapi-generator etc.)."""
    return app.openapi()


class SingularityClient:
    """Typed async client for the Singularity API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8001",
        *,
        api_key: str | None = None,
        transport: httpx.BaseTransport | httpx.AsyncBaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        headers = {"X-API-Key": api_key} if api_key else {}
        self._client = httpx.AsyncClient(
            base_url=base_url, headers=headers, timeout=timeout, transport=transport,
        )

    async def __aenter__(self) -> "SingularityClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    # ── low-level helpers ─────────────────────────────────────────────────────────

    async def _get(self, path: str, **params: Any) -> dict:
        r = await self._client.get(path, params={k: v for k, v in params.items()
                                                  if v is not None})
        r.raise_for_status()
        return r.json()

    async def _post(self, path: str, body: dict) -> dict:
        r = await self._client.post(path, json=body)
        r.raise_for_status()
        return r.json()

    # ── health ────────────────────────────────────────────────────────────────────

    async def health(self) -> dict:
        return await self._get("/health")

    async def healthz(self) -> dict:
        return await self._get("/healthz")

    # ── NLP ───────────────────────────────────────────────────────────────────────

    async def analyze_text(self, text: str, **flags: bool) -> dict:
        return await self._post("/analyze/text", {"text": text, **flags})

    async def sentiment(self, text: str) -> dict:
        return await self._post("/sentiment", {"text": text})

    async def entities(self, text: str) -> dict:
        return await self._post("/entities", {"text": text})

    async def keywords(self, text: str, top_k: int = 10) -> dict:
        return await self._post("/keywords", {"text": text, "top_k": top_k})

    async def summarize(self, text: str, ratio: float | None = None) -> dict:
        body: dict[str, Any] = {"text": text}
        if ratio is not None:
            body["ratio"] = ratio
        return await self._post("/summarize", body)

    async def detect_language(self, text: str) -> dict:
        return await self._post("/language/detect", {"text": text})

    # ── embeddings & vectors ──────────────────────────────────────────────────────

    async def embed(self, text: str) -> dict:
        return await self._post("/embeddings", {"text": text})

    async def similarity(self, text_a: str, text_b: str) -> dict:
        return await self._post("/embeddings/similarity",
                                {"text_a": text_a, "text_b": text_b})

    async def vectors_index(self, documents: list[dict]) -> dict:
        return await self._post("/vectors/index", {"documents": documents})

    async def vectors_search(self, query: str, top_k: int = 5) -> dict:
        return await self._post("/vectors/search", {"query": query, "top_k": top_k})

    # ── RAG (lexical) ─────────────────────────────────────────────────────────────

    async def chunk(self, text: str, **opts: Any) -> dict:
        return await self._post("/chunk", {"text": text, **opts})

    async def retrieve_index(self, documents: list[dict]) -> dict:
        return await self._post("/retrieve/index", {"documents": documents})

    async def retrieve_search(self, query: str, top_k: int = 5) -> dict:
        return await self._post("/retrieve/search", {"query": query, "top_k": top_k})

    async def rerank(self, ranked_lists: list[list[dict]], method: str | None = None) -> dict:
        body: dict[str, Any] = {"ranked_lists": ranked_lists}
        if method is not None:
            body["method"] = method
        return await self._post("/rerank", body)

    # ── utilities ─────────────────────────────────────────────────────────────────

    async def cost_compare(self, prompt: str) -> dict:
        return await self._post("/cost/compare", {"prompt": prompt})

    async def validate(self, text: str, constraints: list[dict]) -> dict:
        return await self._post("/validate", {"text": text, "constraints": constraints})

    async def anonymize(self, text: str) -> dict:
        return await self._post("/anonymize", {"text": text})
