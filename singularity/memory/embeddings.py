"""
Singularity — Offline HashEmbeddingFunction (128-dim).
Funguje bez ONNX, bez externích API klícu.
Kritická oprava z Omega: ONNX model corrupted download.
"""
from __future__ import annotations

import hashlib
import struct


class HashEmbeddingFunction:
    """Deterministická embedding funkce bez externích závislostí."""

    DIM = 128

    # ChromaDB >=0.6 vyžaduje name() a is_legacy() na embedding functions
    def name(self) -> str:
        return "hash-embedding-128"

    def is_legacy(self) -> bool:
        return False

    def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002
        return [self._embed(text) for text in input]

    def _embed(self, text: str) -> list[float]:
        result: list[float] = []
        seed = text.encode("utf-8", errors="replace")
        for i in range(self.DIM):
            chunk = hashlib.sha256(seed + i.to_bytes(2, "little")).digest()[:4]
            val = struct.unpack("<I", chunk)[0] / 0xFFFF_FFFF
            result.append(val * 2.0 - 1.0)
        norm = sum(x * x for x in result) ** 0.5 or 1.0
        return [x / norm for x in result]


def get_embedding_function() -> HashEmbeddingFunction:
    return HashEmbeddingFunction()
