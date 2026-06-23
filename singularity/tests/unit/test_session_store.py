"""Unit testy — SessionStore (Fáze 1)."""
import pytest

from core.session_store import ConversationTurn, Session, SessionStore, estimate_cost


@pytest.mark.unit
def test_estimate_cost_claude():
    response = "a" * 4000   # ~1000 tokenů
    cost = estimate_cost(response, {"plan": "claude", "execute": "claude"})
    assert cost == pytest.approx(0.003, rel=0.1)


@pytest.mark.unit
def test_estimate_cost_gemini():
    response = "a" * 4000
    cost = estimate_cost(response, {"plan": "gemini", "execute": "gemini"})
    assert cost == pytest.approx(0.0005, rel=0.1)


@pytest.mark.unit
def test_estimate_cost_empty_log():
    # Bez provider_log použije default (claude)
    cost = estimate_cost("hello world", {})
    assert cost >= 0.0


@pytest.mark.unit
def test_session_store_get_or_create():
    store = SessionStore()
    s1 = store.get_or_create("alice")
    s2 = store.get_or_create("alice")
    assert s1 is s2
    assert s1.user_id == "alice"


@pytest.mark.unit
def test_session_store_add_turn_accumulates_cost():
    store = SessionStore()
    turn1 = ConversationTurn(
        task="Co je Python?",
        response="Python je jazyk.",
        provider_log={"plan": "claude"},
        risk_score=0.1,
        cost_usd=0.001,
    )
    turn2 = ConversationTurn(
        task="Co je Rust?",
        response="Rust je systémový jazyk.",
        provider_log={"plan": "gemini"},
        risk_score=0.1,
        cost_usd=0.0002,
    )
    store.add_turn("bob", turn1)
    store.add_turn("bob", turn2)
    history = store.get_history("bob")
    assert history["turn_count"] == 2
    assert history["total_cost_usd"] == pytest.approx(0.0012, rel=1e-6)


@pytest.mark.unit
def test_session_store_unknown_user_returns_empty():
    store = SessionStore()
    history = store.get_history("nobody")
    assert history["turn_count"] == 0
    assert history["turns"] == []
    assert history["total_cost_usd"] == 0.0


@pytest.mark.unit
def test_session_store_list_users():
    store = SessionStore()
    store.get_or_create("user1")
    store.get_or_create("user2")
    users = store.list_users()
    assert "user1" in users
    assert "user2" in users
