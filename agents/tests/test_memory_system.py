import math

from agents.core.memory_system import (
    MemorySystem,
    MemoryType,
    OutcomeStatus,
)


def test_keyword_retrieval_finds_stored_entry():
    memory = MemorySystem(vector_dim=3)
    text = "Investigate LLM reasoning failures on math word problems"

    entry_id = memory.store(content=text, memory_type=MemoryType.QUERY)
    result = memory.retrieve(query="math word problems", method="hybrid", top_k=3)

    assert any(e.id == entry_id for e in result.entries)
    assert result.method == "hybrid"
    assert len(result.entries) >= 1


def test_vector_retrieval_prefers_closer_embedding():
    memory = MemorySystem(vector_dim=3)
    id_a = memory.store(
        content="Vector A",
        memory_type=MemoryType.FACT,
        embedding=[1.0, 0.0, 0.0],
    )
    memory.store(
        content="Vector B",
        memory_type=MemoryType.FACT,
        embedding=[0.0, 1.0, 0.0],
    )

    result = memory.retrieve(
        query="unused",
        method="vector",
        embedding=[0.9, 0.1, 0.0],
        top_k=2,
    )

    assert len(result.entries) == 2
    assert result.entries[0].id == id_a  # closer to first vector
    assert result.scores[0] >= result.scores[1]
    assert math.isclose(result.scores[0], 0.9938837346736189, rel_tol=1e-9)


def test_store_episode_respects_window_and_persists_memory():
    memory = MemorySystem(episodic_window=1)
    memory.store_episode(
        query="Find prime numbers",
        reasoning_steps=["check divisibility"],
        tools_used=["calculator"],
        outcome=OutcomeStatus.SUCCESS,
        confidence=0.9,
    )
    memory.store_episode(
        query="Find prime numbers quickly",
        reasoning_steps=["use sieve"],
        tools_used=["script"],
        outcome=OutcomeStatus.SUCCESS,
        confidence=0.95,
    )

    # Window of 1 keeps only the latest episode
    assert len(memory.episodic_memories) == 1
    # Query was also stored in general memories
    assert memory.memories


def test_should_avoid_triggers_on_repeat_failures():
    memory = MemorySystem()
    for _ in range(2):
        memory.store_episode(
            query="Solve the tricky integral",
            reasoning_steps=["integration by parts"],
            tools_used=["symbolic"],
            outcome=OutcomeStatus.FAILURE,
            confidence=0.2,
        )

    avoid, reason = memory.should_avoid("Solve the tricky integral now")

    assert avoid is True
    assert reason and "failed" in reason.lower()
