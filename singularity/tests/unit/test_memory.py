"""Unit testy paměti — lokální ChromaDB backend bez API klíčů."""
from __future__ import annotations

import pytest

from memory.embeddings import HashEmbeddingFunction

pytestmark = pytest.mark.unit


def test_hash_embedding_dimension():
    ef = HashEmbeddingFunction()
    vectors = ef(["ahoj svete"])
    assert len(vectors) == 1
    assert len(vectors[0]) == HashEmbeddingFunction.DIM


def test_hash_embedding_deterministic():
    ef = HashEmbeddingFunction()
    a = ef(["stejny text"])[0]
    b = ef(["stejny text"])[0]
    assert a == b


def test_hash_embedding_normalized():
    ef = HashEmbeddingFunction()
    vec = ef(["test"])[0]
    norm = sum(x * x for x in vec) ** 0.5
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_different_texts_differ():
    ef = HashEmbeddingFunction()
    assert ef(["text a"])[0] != ef(["text b"])[0]
