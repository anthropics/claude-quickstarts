"""
Singularity — shared runtime singletons.

Extracted from api/main.py as part of the maintainability refactor: modules
under api/routers/ import their dependencies from here rather than from
api.main (which would be a circular import). As more endpoint groups move out
of the main.py monolith, their singletons migrate here.

These objects are built once at import and never reassigned, so importing them
by name yields a stable shared reference.
"""

from __future__ import annotations

from config.settings import settings
from core.coalescer import SingleFlight
from core.embeddings import build_embedding_provider
from core.state_store import build_state_store
from core.streaming import StreamMetrics
from core.tenancy import TenantRegistry
from core.vector_store import VectorStore

# Embedding Provider (Fáze 61, v2.0) — pluggable, offline feature-hashing
# default with lexical locality; swap for an API-backed provider in production.
embedding_provider = build_embedding_provider(
    settings.embedding_provider,
    dim=settings.embedding_dim,
    ngram=settings.embedding_ngram,
    cache_size=settings.embedding_cache_size,
)

# Vector Store (Fáze 69, v2.0 #9) — dense retriever sharing the embedding
# provider; semantic complement to BM25 (Fáze 37).
vector_store: VectorStore = VectorStore(embedder=embedding_provider)

# State Store (Fáze 62, v2.0) — backend-agnostic shared state; defaults to
# in-memory, swappable to Redis for multi-instance.
state_store = build_state_store(settings.state_backend, redis_url=settings.redis_url)

# Token-streaming metrics (Fáze 64), tenant registry (Fáze 65), request
# coalescer (Fáze 66) — each owned by its api/routers/* module.
stream_metrics: StreamMetrics = StreamMetrics()
tenants: TenantRegistry = TenantRegistry()
coalescer: SingleFlight = SingleFlight()
