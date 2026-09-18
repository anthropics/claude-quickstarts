"""
Unit tests — Context Window Manager (Fáze 32).

Fully offline. Token counts use the deterministic word-based estimator
(or an injected count_fn) so budgets are predictable.
"""

from __future__ import annotations

import pytest

from core.context_manager import (
    ContextWindowManager,
    TrimResult,
    TrimStrategy,
    estimate_tokens,
)


# A count_fn where every message counts as exactly 10 tokens — easy budgeting.
def _ten(_text: str) -> int:
    return 10


def _msgs(*roles_contents):
    return [{"role": r, "content": c} for r, c in roles_contents]


# ── estimate_tokens ─────────────────────────────────────────────────────────────

def test_estimate_tokens_empty():
    assert estimate_tokens("") == 0


def test_estimate_tokens_words():
    assert estimate_tokens("one two three") == int(3 * 1.3)


def test_estimate_tokens_none_safe():
    assert estimate_tokens(None) == 0


# ── Construction validation ──────────────────────────────────────────────────────

def test_invalid_max_tokens_raises():
    with pytest.raises(ValueError):
        ContextWindowManager(max_tokens=0)


def test_invalid_keep_recent_raises():
    with pytest.raises(ValueError):
        ContextWindowManager(keep_recent=-1)


# ── count_messages ──────────────────────────────────────────────────────────────

def test_count_messages_sums():
    cm = ContextWindowManager(count_fn=_ten)
    assert cm.count_messages(_msgs(("user", "a"), ("assistant", "b"))) == 20


# ── No trimming when under budget ────────────────────────────────────────────────

def test_fit_no_trim_when_under_budget():
    cm = ContextWindowManager(max_tokens=100, count_fn=_ten)
    msgs = _msgs(("user", "a"), ("assistant", "b"))
    result = cm.fit(msgs)
    assert result.within_budget
    assert result.dropped_count == 0
    assert result.messages == msgs
    assert "No trimming needed" in result.notes


# ── DROP_OLDEST ──────────────────────────────────────────────────────────────────

def test_drop_oldest_removes_oldest_non_system():
    # 6 messages × 10 = 60 tokens; budget 30 → must drop down to 3 messages
    cm = ContextWindowManager(
        max_tokens=30, keep_recent=2, strategy=TrimStrategy.DROP_OLDEST, count_fn=_ten
    )
    msgs = _msgs(
        ("user", "u1"), ("assistant", "a1"),
        ("user", "u2"), ("assistant", "a2"),
        ("user", "u3"), ("assistant", "a3"),
    )
    result = cm.fit(msgs)
    assert result.within_budget
    assert result.final_tokens <= 30
    # last 2 must survive
    assert result.messages[-1]["content"] == "a3"
    assert result.messages[-2]["content"] == "u3"
    assert result.dropped_count >= 3


def test_drop_oldest_preserves_system():
    cm = ContextWindowManager(
        max_tokens=20, keep_recent=1, strategy=TrimStrategy.DROP_OLDEST, count_fn=_ten
    )
    msgs = _msgs(
        ("system", "sys"),
        ("user", "u1"), ("assistant", "a1"),
        ("user", "u2"), ("assistant", "a2"),
    )
    result = cm.fit(msgs)
    # system always kept
    assert any(m["role"] == "system" and m["content"] == "sys" for m in result.messages)
    # most recent kept
    assert result.messages[-1]["content"] == "a2"


def test_drop_oldest_budget_unreachable_keeps_protected():
    # system + recent already exceed budget → within_budget False but protected kept
    cm = ContextWindowManager(
        max_tokens=5, keep_recent=2, strategy=TrimStrategy.DROP_OLDEST, count_fn=_ten
    )
    msgs = _msgs(("system", "s"), ("user", "u1"), ("assistant", "a1"))
    result = cm.fit(msgs)
    assert result.within_budget is False
    assert any(m["role"] == "system" for m in result.messages)


# ── SUMMARIZE_OLDEST ─────────────────────────────────────────────────────────────

def test_summarize_inserts_summary_note():
    cm = ContextWindowManager(
        max_tokens=30, keep_recent=2, strategy=TrimStrategy.SUMMARIZE_OLDEST, count_fn=_ten
    )
    msgs = _msgs(
        ("user", "first message here"), ("assistant", "reply one"),
        ("user", "second"), ("assistant", "reply two"),
        ("user", "third"), ("assistant", "reply three"),
    )
    result = cm.fit(msgs)
    assert result.summarized is True
    assert any("summary" in m["content"].lower() for m in result.messages)


def test_summarize_places_note_after_system():
    cm = ContextWindowManager(
        max_tokens=30, keep_recent=1, strategy=TrimStrategy.SUMMARIZE_OLDEST, count_fn=_ten
    )
    msgs = _msgs(
        ("system", "sys"),
        ("user", "u1"), ("assistant", "a1"),
        ("user", "u2"), ("assistant", "a2"),
    )
    result = cm.fit(msgs)
    # first message still the system prompt
    assert result.messages[0]["role"] == "system"
    assert result.messages[0]["content"] == "sys"
    # summary note comes right after
    assert "summary" in result.messages[1]["content"].lower()


# ── KEEP_RECENT ──────────────────────────────────────────────────────────────────

def test_keep_recent_hard_cut():
    cm = ContextWindowManager(
        max_tokens=10, keep_recent=2, strategy=TrimStrategy.KEEP_RECENT, count_fn=_ten
    )
    msgs = _msgs(
        ("user", "u1"), ("assistant", "a1"),
        ("user", "u2"), ("assistant", "a2"),
        ("user", "u3"), ("assistant", "a3"),
    )
    result = cm.fit(msgs)
    assert len(result.messages) == 2
    assert result.messages[0]["content"] == "u3"
    assert result.messages[1]["content"] == "a3"


def test_keep_recent_includes_system():
    cm = ContextWindowManager(
        max_tokens=10, keep_recent=1, strategy=TrimStrategy.KEEP_RECENT, count_fn=_ten
    )
    msgs = _msgs(
        ("system", "sys"),
        ("user", "u1"), ("assistant", "a1"), ("user", "u2"),
    )
    result = cm.fit(msgs)
    roles = [m["role"] for m in result.messages]
    assert "system" in roles
    assert result.messages[-1]["content"] == "u2"


# ── Strategy override per call ───────────────────────────────────────────────────

def test_fit_strategy_override():
    cm = ContextWindowManager(
        max_tokens=10, keep_recent=1, strategy=TrimStrategy.DROP_OLDEST, count_fn=_ten
    )
    msgs = _msgs(("user", "u1"), ("assistant", "a1"), ("user", "u2"))
    result = cm.fit(msgs, strategy=TrimStrategy.KEEP_RECENT)
    assert result.strategy == TrimStrategy.KEEP_RECENT


# ── TrimResult shape ─────────────────────────────────────────────────────────────

def test_result_to_dict_shape():
    cm = ContextWindowManager(max_tokens=10, count_fn=_ten)
    result = cm.fit(_msgs(("user", "u1"), ("assistant", "a1"), ("user", "u2")))
    d = result.to_dict()
    for key in ("messages", "original_tokens", "final_tokens", "dropped_count",
                "summarized", "strategy", "within_budget", "notes"):
        assert key in d
    assert d["strategy"] == "drop_oldest"


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_no_trim():
    cm = ContextWindowManager(max_tokens=1000, count_fn=_ten)
    cm.fit(_msgs(("user", "a")))
    m = cm.metrics()
    assert m["total_calls"] == 1
    assert m["total_trimmed"] == 0
    assert m["trim_rate"] == 0.0


def test_metrics_after_trim():
    cm = ContextWindowManager(max_tokens=10, keep_recent=1, count_fn=_ten)
    cm.fit(_msgs(("user", "u1"), ("assistant", "a1"), ("user", "u2")))
    m = cm.metrics()
    assert m["total_trimmed"] == 1
    assert m["total_dropped_messages"] >= 1
    assert m["trim_rate"] == 1.0


def test_metrics_summarized_counted():
    cm = ContextWindowManager(
        max_tokens=20, keep_recent=1, strategy=TrimStrategy.SUMMARIZE_OLDEST, count_fn=_ten
    )
    cm.fit(_msgs(
        ("user", "u1"), ("assistant", "a1"),
        ("user", "u2"), ("assistant", "a2"),
    ))
    assert cm.metrics()["total_summarized"] == 1


def test_metrics_reset():
    cm = ContextWindowManager(max_tokens=10, keep_recent=1, count_fn=_ten)
    cm.fit(_msgs(("user", "u1"), ("assistant", "a1"), ("user", "u2")))
    cm.reset_metrics()
    m = cm.metrics()
    assert m["total_calls"] == 0
    assert m["total_dropped_messages"] == 0


def test_metrics_shape():
    cm = ContextWindowManager(count_fn=_ten)
    m = cm.metrics()
    for key in ("total_calls", "total_trimmed", "total_dropped_messages",
                "total_summarized", "trim_rate", "max_tokens", "keep_recent"):
        assert key in m


# ── Edge cases ──────────────────────────────────────────────────────────────────

def test_empty_messages():
    cm = ContextWindowManager(max_tokens=10, count_fn=_ten)
    result = cm.fit([])
    assert result.messages == []
    assert result.within_budget is True


def test_all_system_messages_kept():
    cm = ContextWindowManager(max_tokens=10, keep_recent=0, count_fn=_ten)
    msgs = _msgs(("system", "s1"), ("system", "s2"), ("system", "s3"))
    result = cm.fit(msgs)
    # nothing droppable → all system kept, over budget
    assert len(result.messages) == 3
    assert result.within_budget is False


def test_keep_recent_zero_drops_all_non_system():
    cm = ContextWindowManager(
        max_tokens=10, keep_recent=0, strategy=TrimStrategy.DROP_OLDEST, count_fn=_ten
    )
    msgs = _msgs(("system", "s"), ("user", "u1"), ("assistant", "a1"), ("user", "u2"))
    result = cm.fit(msgs)
    # only system survives (10 tokens == budget)
    assert all(m["role"] == "system" for m in result.messages)
    assert result.within_budget is True
