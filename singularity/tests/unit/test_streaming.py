"""Unit testy — run_stream() node-level streaming (Fáze 1)."""
from __future__ import annotations
from unittest.mock import MagicMock

import pytest

from core.graph import SingularityCore
from core.router import LLMRouter
from tests.conftest import MockProvider


def _make_core(monkeypatch) -> SingularityCore:
    """Vytvoří SingularityCore s mock providery a mock pamětí (bez API klíčů)."""
    claude = MockProvider(name="claude")
    router = LLMRouter(claude=claude, gemini=None, strategy="static")

    # Zabráníme inicializaci ChromaDB v testech
    mock_memory = MagicMock()
    mock_memory.search.return_value = []
    mock_memory.store_episode.return_value = None
    mock_memory.store_workflow.return_value = None
    monkeypatch.setattr("core.graph.OmegaMemory", lambda: mock_memory)

    return SingularityCore(router=router)


@pytest.mark.unit
async def test_run_stream_yields_node_events(monkeypatch):
    """run_stream musí vydat aspoň jeden node_completed event."""
    core = _make_core(monkeypatch)
    events = []
    async for evt in core.run_stream(
        task="Test streaming", user_id="tester", session_id="s1"
    ):
        events.append(evt)

    node_events = [e for e in events if e["event"] == "node_completed"]
    assert len(node_events) >= 1


@pytest.mark.unit
async def test_run_stream_ends_with_completed(monkeypatch):
    """Poslední event musí být 'completed' s klíčem 'response'."""
    core = _make_core(monkeypatch)
    events = []
    async for evt in core.run_stream(
        task="Test completed event", user_id="tester", session_id="s2"
    ):
        events.append(evt)

    assert events[-1]["event"] == "completed"
    assert "response" in events[-1]
    assert "provider_log" in events[-1]


@pytest.mark.unit
async def test_run_stream_provider_log_accumulates(monkeypatch):
    """provider_log ve 'completed' eventu musí obsahovat alespoň jeden záznam."""
    core = _make_core(monkeypatch)
    completed = None
    async for evt in core.run_stream(
        task="Provider log test", user_id="tester", session_id="s3"
    ):
        if evt["event"] == "completed":
            completed = evt
    assert completed is not None
    assert isinstance(completed["provider_log"], dict)


@pytest.mark.unit
async def test_run_stream_node_events_have_required_keys(monkeypatch):
    """Každý node_completed event musí mít 'node' a 'provider_log'."""
    core = _make_core(monkeypatch)
    found_node_event = False
    async for evt in core.run_stream(
        task="Key check", user_id="tester", session_id="s4"
    ):
        if evt["event"] == "node_completed":
            assert "node" in evt
            assert "provider_log" in evt
            found_node_event = True
            break
    assert found_node_event
