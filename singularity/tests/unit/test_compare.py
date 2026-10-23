"""Unit testy — provider comparison a session export (Fáze 3)."""
import pytest

from core.session_store import ConversationTurn, SessionStore


@pytest.mark.unit
def test_conversation_turn_has_eval_scores_field():
    turn = ConversationTurn(
        task="T",
        response="R",
        provider_log={"plan": "claude"},
        risk_score=0.1,
        cost_usd=0.001,
        eval_scores={"relevance": 0.9, "coherence": 0.85},
    )
    assert turn.eval_scores["relevance"] == pytest.approx(0.9)


@pytest.mark.unit
def test_conversation_turn_eval_scores_default_empty():
    turn = ConversationTurn(
        task="T",
        response="R",
        provider_log={},
        risk_score=0.0,
        cost_usd=0.0,
    )
    assert turn.eval_scores == {}


@pytest.mark.unit
def test_session_export_includes_eval_scores():
    store = SessionStore()
    store.add_turn(
        "carol",
        ConversationTurn(
            task="Explain X",
            response="X is Y",
            provider_log={"plan": "claude"},
            risk_score=0.1,
            cost_usd=0.0005,
            eval_scores={"relevance": 0.95},
        ),
    )
    history = store.get_history("carol")
    assert history["turns"][0]["eval_scores"]["relevance"] == pytest.approx(0.95)


@pytest.mark.unit
def test_session_export_json_serializable():
    import json

    store = SessionStore()
    store.add_turn(
        "dave",
        ConversationTurn(
            task="Q",
            response="A",
            provider_log={"plan": "gemini"},
            risk_score=0.2,
            cost_usd=0.0001,
        ),
    )
    history = store.get_history("dave")
    # Musí být JSON serializovatelné bez výjimky
    payload = json.dumps(history, ensure_ascii=False)
    assert "dave" in payload


@pytest.mark.unit
def test_session_export_empty_user():
    import json

    store = SessionStore()
    history = store.get_history("nobody")
    payload = json.dumps(history, ensure_ascii=False)
    data = json.loads(payload)
    assert data["turn_count"] == 0
