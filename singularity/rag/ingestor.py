"""
Singularity — RAG ingestor (LlamaIndex + ChromaDB).
Volitelná komponenta — pokud llama-index není nainstalován, degraduje na no-op.
"""
from __future__ import annotations

import structlog

log = structlog.get_logger()


class OmegaRAG:
    def __init__(self, persist_dir: str = "./data/chroma") -> None:
        self._persist_dir = persist_dir
        self._index = None
        try:
            import llama_index.core  # noqa: F401

            self._available = True
            log.info("rag_init", persist_dir=persist_dir)
        except ImportError:
            self._available = False
            log.warning("rag_unavailable", reason="llama_index not installed")

    def ingest(self, data_dir: str) -> None:
        if not self._available:
            return
        from llama_index.core import SimpleDirectoryReader, VectorStoreIndex

        docs = SimpleDirectoryReader(data_dir).load_data()
        self._index = VectorStoreIndex.from_documents(docs)
        log.info("rag_ingest_done", doc_count=len(docs))

    def query(self, text: str, top_k: int = 3) -> str:
        if not self._available or self._index is None:
            return ""
        try:
            engine = self._index.as_query_engine(similarity_top_k=top_k)
            return str(engine.query(text))
        except Exception as exc:
            log.warning("rag_query_failed", error=str(exc))
            return ""
