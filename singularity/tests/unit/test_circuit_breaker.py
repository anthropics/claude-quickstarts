"""
Tests for CircuitBreakerRegistry (Fáze 25).
All offline — no external dependencies.
Time-based recovery tested via monkeypatching time.monotonic.
"""
import time
import pytest
from unittest.mock import patch

from core.circuit_breaker import CircuitBreakerRegistry, CircuitState


@pytest.fixture
def reg():
    return CircuitBreakerRegistry()


def _cb(reg, name="svc", failure_threshold=3, recovery_timeout_s=60.0, success_threshold=2):
    return reg.get_or_create(
        name,
        failure_threshold=failure_threshold,
        recovery_timeout_s=recovery_timeout_s,
        success_threshold=success_threshold,
    )


# ── Validation ────────────────────────────────────────────────────────────────

def test_empty_name_raises(reg):
    with pytest.raises(ValueError, match="name"):
        reg.get_or_create("")


def test_zero_failure_threshold_raises(reg):
    with pytest.raises(ValueError, match="failure_threshold"):
        reg.get_or_create("x", failure_threshold=0)


def test_negative_recovery_timeout_raises(reg):
    with pytest.raises(ValueError, match="recovery_timeout_s"):
        reg.get_or_create("x", recovery_timeout_s=0)


def test_zero_success_threshold_raises(reg):
    with pytest.raises(ValueError, match="success_threshold"):
        reg.get_or_create("x", success_threshold=0)


# ── Initial state ─────────────────────────────────────────────────────────────

def test_new_breaker_is_closed(reg):
    _cb(reg)
    assert reg.is_open("svc") is False
    assert reg.get_state("svc")["state"] == "closed"


def test_unknown_breaker_not_open(reg):
    assert reg.is_open("ghost") is False


def test_get_state_missing_returns_none(reg):
    assert reg.get_state("ghost") is None


def test_breaker_count(reg):
    _cb(reg, "a")
    _cb(reg, "b")
    assert reg.breaker_count() == 2


def test_get_or_create_idempotent(reg):
    cb1 = _cb(reg)
    cb2 = _cb(reg)
    assert cb1 is cb2


# ── CLOSED → OPEN transition ──────────────────────────────────────────────────

def test_failures_below_threshold_stays_closed(reg):
    _cb(reg, failure_threshold=3)
    reg.record_failure("svc")
    reg.record_failure("svc")
    assert reg.is_open("svc") is False


def test_failures_at_threshold_opens(reg):
    _cb(reg, failure_threshold=3)
    reg.record_failure("svc")
    reg.record_failure("svc")
    reg.record_failure("svc")
    assert reg.is_open("svc") is True
    assert reg.get_state("svc")["state"] == "open"


def test_open_rejects_and_counts(reg):
    _cb(reg, failure_threshold=1)
    reg.record_failure("svc")
    assert reg.is_open("svc") is True
    reg.record_rejected("svc")
    assert reg.get_state("svc")["total_rejected"] == 1


# ── OPEN → HALF_OPEN transition ───────────────────────────────────────────────

def test_recovery_timeout_transitions_to_half_open(reg):
    _cb(reg, failure_threshold=1, recovery_timeout_s=0.05)
    reg.record_failure("svc")
    assert reg.is_open("svc") is True
    time.sleep(0.1)
    # After timeout, is_open() should return False (probe allowed)
    assert reg.is_open("svc") is False
    assert reg.get_state("svc")["state"] == "half_open"


# ── HALF_OPEN → CLOSED transition ─────────────────────────────────────────────

def test_success_in_half_open_closes_after_threshold(reg):
    _cb(reg, failure_threshold=1, recovery_timeout_s=0.05, success_threshold=2)
    reg.record_failure("svc")
    time.sleep(0.1)
    reg.is_open("svc")  # trigger HALF_OPEN transition
    reg.record_success("svc")
    assert reg.get_state("svc")["state"] == "half_open"  # need 2
    reg.record_success("svc")
    assert reg.get_state("svc")["state"] == "closed"


# ── HALF_OPEN → OPEN on failure ───────────────────────────────────────────────

def test_failure_in_half_open_reopens(reg):
    _cb(reg, failure_threshold=1, recovery_timeout_s=0.05, success_threshold=2)
    reg.record_failure("svc")
    time.sleep(0.1)
    reg.is_open("svc")  # trigger HALF_OPEN
    reg.record_failure("svc")
    assert reg.get_state("svc")["state"] == "open"


# ── Reset ─────────────────────────────────────────────────────────────────────

def test_reset_closes_open_breaker(reg):
    _cb(reg, failure_threshold=1)
    reg.record_failure("svc")
    assert reg.is_open("svc") is True
    reg.reset("svc")
    assert reg.is_open("svc") is False
    assert reg.get_state("svc")["state"] == "closed"


def test_reset_missing_returns_false(reg):
    assert reg.reset("ghost") is False


# ── Counters ──────────────────────────────────────────────────────────────────

def test_total_counters(reg):
    _cb(reg, failure_threshold=10)
    reg.record_success("svc")
    reg.record_success("svc")
    reg.record_failure("svc")
    s = reg.get_state("svc")
    assert s["total_successes"] == 2
    assert s["total_failures"] == 1


def test_list_breakers(reg):
    _cb(reg, "a")
    _cb(reg, "b")
    names = {d["name"] for d in reg.list_breakers()}
    assert names == {"a", "b"}
