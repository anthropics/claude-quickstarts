"""
Singularity — OmegaMemory (port z Omega, zachovány všechny kritické opravy).

Kritické opravy:
  - Mem0 crash bez OpenAI embeddings → _LocalMemoryStore s HashEmbeddingFunction
  - ONNX model corrupted download → offline HashEmbeddingFunction (128-dim)
  - keyword arg conflict v mock fixture → keyword-only *, user_id
"""
from __future__ import annotations

import os
import uuid
import structlog

log = structlog.get_logger()

_OPENAI_AVAILABLE = bool(os.environ.get("OPENAI_API_KEY", "").strip())
_MEM0_CLOUD       = bool(os.environ.get("MEM0_API_KEY",  "").strip())


class _LocalMemoryStore:
    def __init__(self, persist_dir: str) -> None:
        import chromadb
        from chromadb.config import Settings as CSettings
        from memory.embeddings import get_embedding_function

        self._ef = get_embedding_function()
        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=CSettings(anonymized_telemetry=False),
        )
        self._col = self._client.get_or_create_collection(
            "singularity_memory",
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )
        log.info("local_memory_store_init", persist_dir=persist_dir)

    # keyword-only user_id — oprava konfliktu v mock fixture
    def add(self, content: str, *, user_id: str, metadata: dict | None = None) -> str:
        doc_id = f"{user_id}_{uuid.uuid4().hex[:12]}"
        self._col.add(
            documents=[content],
            metadatas=[{"user_id": user_id, **(metadata or {})}],
            ids=[doc_id],
        )
        return doc_id

    def search(self, query: str, *, user_id: str, limit: int = 5) -> list[dict]:
        try:
            count = self._col.count()
            if count == 0:
                return []
            results = self._col.query(
                query_texts=[query],
                n_results=min(limit * 2, count),
                where={"user_id": user_id},
            )
            docs  = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            return [{"memory": d, "metadata": m} for d, m in zip(docs, metas)][:limit]
        except Exception as exc:
            log.warning("local_search_failed", error=str(exc))
            return []

    def get_all(self, *, user_id: str) -> list[dict]:
        try:
            results = self._col.get(where={"user_id": user_id})
            docs  = results.get("documents") or []
            metas = results.get("metadatas") or []
            return [{"memory": d, "metadata": m} for d, m in zip(docs, metas)]
        except Exception as exc:
            log.warning("local_get_all_failed", error=str(exc))
            return []


class OmegaMemory:
    """Třívrstvá paměť: epizodická, sémantická, procedurální."""

    def __init__(self) -> None:
        from config.settings import settings

        if _MEM0_CLOUD:
            from mem0 import MemoryClient
            self._store = MemoryClient(api_key=os.environ["MEM0_API_KEY"])
            self._mode = "mem0_cloud"
        elif _OPENAI_AVAILABLE:
            from mem0 import Memory
            self._store = Memory()
            self._mode = "mem0_openai"
        else:
            self._store = _LocalMemoryStore(settings.chroma_persist_dir)
            self._mode = "local"

        log.info("memory_init", mode=self._mode)

    def search(self, query: str, user_id: str, limit: int = 5) -> list[dict]:
        try:
            if self._mode == "local":
                return self._store.search(query, user_id=user_id, limit=limit)  # type: ignore[union-attr]
            return self._store.search(query, user_id=user_id, limit=limit)
        except Exception as exc:
            log.warning("memory_search_failed", error=str(exc))
            return []

    def store_episode(self, content: str, user_id: str, session_id: str) -> None:
        try:
            meta = {"type": "episode", "session_id": session_id}
            if self._mode == "local":
                self._store.add(content, user_id=user_id, metadata=meta)  # type: ignore[union-attr]
            else:
                self._store.add(content, user_id=user_id, metadata=meta)
        except Exception as exc:
            log.warning("episode_store_failed", error=str(exc))

    def store_workflow(self, name: str, steps: list[str], user_id: str) -> None:
        try:
            content = f"WORKFLOW: {name}\n" + "\n".join(steps)
            meta = {"type": "workflow", "name": name}
            if self._mode == "local":
                self._store.add(content, user_id=user_id, metadata=meta)  # type: ignore[union-attr]
            else:
                self._store.add(content, user_id=user_id, metadata=meta)
        except Exception as exc:
            log.warning("workflow_store_failed", error=str(exc))

    def get_all(self, user_id: str) -> list[dict]:
        try:
            if self._mode == "local":
                return self._store.get_all(user_id=user_id)  # type: ignore[union-attr]
            return self._store.get_all(user_id=user_id)
        except Exception as exc:
            log.warning("get_all_failed", error=str(exc))
            return []
