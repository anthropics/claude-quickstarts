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
from core.embeddings import build_embedding_provider
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
