"""Unit testy — multi-turn session kontext (Fáze 2)."""
from unittest.mock import MagicMock

import pytest

from core.session_store import ConversationTurn, SessionStore


def _store_with_turns(n: int) -> SessionStore:
    store = SessionStore()
    for i in range(n):
        store.add_turn(
            "alice",
            ConversationTurn(
                task=f"Otázka {i + 1}",
                response=f"Odpověď {i + 1}",
                provider_log={"plan": "claude"},
                risk_score=0.1,
                cost_usd=0.0001,
            ),
        )
    return store


@pytest.mark.unit
def test_session_context_empty_when_no_history():
    """Bez předchozích turnů vrátí _build_session_context prázdný řetězec."""
    store = SessionStore()
    history = store.get_history("nobody")
    turns = history["turns"][-3:]
    assert turns == []


@pytest.mark.unit
def test_session_context_contains_recent_turns():
    store = _store_with_turns(5)
    history = store.get_history("alice")
    turns = history["turns"][-3:]   # max 3 turny
    assert len(turns) == 3
    # Poslední turn musí být Turn 5
    assert "Otázka 5" in turns[-1]["task"]


@pytest.mark.unit
def test_session_context_max_3_turns():
    store = _store_with_turns(10)
    history = store.get_history("alice")
    turns = history["turns"][-3:]
    assert len(turns) == 3


@pytest.mark.unit
def test_session_context_format():
    """Zkontroluje, že formátování kontextu obsahuje task a response."""
    store = _store_with_turns(2)
    history = store.get_history("alice")
    turns = history["turns"][-3:]
    ctx = "\n".join(
        f"[Turn {i + 1}]\nTask: {t['task']}\nResponse: {t['response'][:300]}"
        for i, t in enumerate(turns)
    )
    assert "[Turn 1]" in ctx
    assert "Otázka 1" in ctx
    assert "Odpověď 1" in ctx


@pytest.mark.unit
def test_cumulative_cost_across_turns():
    store = _store_with_turns(4)
    history = store.get_history("alice")
    assert history["total_cost_usd"] == pytest.approx(4 * 0.0001, rel=1e-6)
