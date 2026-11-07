"""
Singularity — Pomocný vector store wrapper pro RAG (ChromaDB + offline embeddings).
"""
from __future__ import annotations

import structlog

log = structlog.get_logger()


class SingularityVectorStore:
    def __init__(self, persist_dir: str = "./data/chroma") -> None:
        import chromadb
        from chromadb.config import Settings

        from memory.embeddings import get_embedding_function

        self._ef = get_embedding_function()
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self._col = self._client.get_or_create_collection(
            "singularity_rag",
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(self, docs: list[str], ids: list[str] | None = None) -> None:
        used_ids = ids or [f"doc_{i}" for i in range(len(docs))]
        self._col.upsert(documents=docs, ids=used_ids)
        log.info("docs_added", count=len(docs))

    def query(self, text: str, n_results: int = 3) -> list[str]:
        count = self._col.count()
        if count == 0:
            return []
        results = self._col.query(query_texts=[text], n_results=min(n_results, count))
        return results.get("documents", [[]])[0]
