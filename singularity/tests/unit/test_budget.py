"""Unit testy — BudgetManager per-user cost limity (Fáze 4)."""
import pytest

from core.budget_manager import BudgetManager


@pytest.mark.unit
def test_default_no_limit_allows_all():
    bm = BudgetManager()
    assert bm.is_allowed("alice") is True
    assert bm.is_allowed("alice", estimated_cost=9999.0) is True


@pytest.mark.unit
def test_set_budget_blocks_over_limit():
    bm = BudgetManager()
    bm.set_budget("bob", 1.0)
    bm.record_spend("bob", 0.9)
    assert bm.is_allowed("bob", estimated_cost=0.05) is True
    assert bm.is_allowed("bob", estimated_cost=0.15) is False


@pytest.mark.unit
def test_record_spend_accumulates():
    bm = BudgetManager()
    bm.set_budget("carol", 2.0)
    bm.record_spend("carol", 0.5)
    bm.record_spend("carol", 0.5)
    status = bm.get_status("carol")
    assert status["spent_usd"] == pytest.approx(1.0)
    assert status["remaining_usd"] == pytest.approx(1.0)
    assert status["over_budget"] is False


@pytest.mark.unit
def test_reset_spent_clears_balance():
    bm = BudgetManager()
    bm.set_budget("dave", 1.0)
    bm.record_spend("dave", 0.8)
    bm.reset_spent("dave")
    status = bm.get_status("dave")
    assert status["spent_usd"] == pytest.approx(0.0)
    assert status["over_budget"] is False


@pytest.mark.unit
def test_set_budget_zero_removes_limit():
    bm = BudgetManager()
    bm.set_budget("eve", 0.5)
    bm.set_budget("eve", 0.0)  # smaže limit
    assert bm.is_allowed("eve", estimated_cost=9999.0) is True
    status = bm.get_status("eve")
    assert status["limit_usd"] is None
