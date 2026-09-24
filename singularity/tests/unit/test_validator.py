"""
Unit tests — Output Validator (Fáze 31).

Fully offline. invoke_fn is supplied as an async function returning
deterministic responses (optionally varying per attempt).
"""

from __future__ import annotations

import asyncio
import json
import pytest

from core.validator import (
    BannedWordsConstraint,
    ConstraintResult,
    JSONConstraint,
    LengthConstraint,
    NonEmptyConstraint,
    OutputValidator,
    PredicateConstraint,
    RegexConstraint,
    ValidationResult,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _const(value: str):
    async def _inv(messages):
        return value
    return _inv


def _sequence(*values: str):
    """invoke_fn that returns a different value on each call."""
    calls = {"n": 0}

    async def _inv(messages):
        v = values[min(calls["n"], len(values) - 1)]
        calls["n"] += 1
        return v
    return _inv


# ── Constraints: NonEmpty ─────────────────────────────────────────────────────

def test_non_empty_passes():
    r = NonEmptyConstraint().check("hello")
    assert r.passed


def test_non_empty_fails_on_blank():
    r = NonEmptyConstraint().check("   ")
    assert not r.passed
    assert "empty" in r.message.lower()


# ── Constraints: JSON ─────────────────────────────────────────────────────────

def test_json_valid():
    assert JSONConstraint().check('{"a": 1}').passed


def test_json_invalid():
    r = JSONConstraint().check("not json")
    assert not r.passed
    assert "Invalid JSON" in r.message


def test_json_required_keys_present():
    assert JSONConstraint(["a", "b"]).check('{"a":1,"b":2}').passed


def test_json_required_keys_missing():
    r = JSONConstraint(["a", "b"]).check('{"a":1}')
    assert not r.passed
    assert "b" in r.message


def test_json_required_keys_non_object():
    r = JSONConstraint(["a"]).check("[1,2,3]")
    assert not r.passed
    assert "object" in r.message


# ── Constraints: Length ───────────────────────────────────────────────────────

def test_length_within_bounds():
    assert LengthConstraint(min_len=2, max_len=10).check("hello").passed


def test_length_too_short():
    r = LengthConstraint(min_len=5).check("ab")
    assert not r.passed
    assert "Too short" in r.message


def test_length_too_long():
    r = LengthConstraint(max_len=3).check("abcdef")
    assert not r.passed
    assert "Too long" in r.message


def test_length_invalid_min_raises():
    with pytest.raises(ValueError):
        LengthConstraint(min_len=-1)


def test_length_invalid_max_raises():
    with pytest.raises(ValueError):
        LengthConstraint(min_len=10, max_len=5)


# ── Constraints: Regex ────────────────────────────────────────────────────────

def test_regex_should_match_pass():
    assert RegexConstraint(r"\d{3}").check("abc 123").passed


def test_regex_should_match_fail():
    r = RegexConstraint(r"\d{3}").check("no digits")
    assert not r.passed


def test_regex_should_not_match():
    assert RegexConstraint(r"\d", should_match=False).check("letters").passed


def test_regex_should_not_match_fail():
    r = RegexConstraint(r"\d", should_match=False).check("has 1 digit")
    assert not r.passed


# ── Constraints: BannedWords ──────────────────────────────────────────────────

def test_banned_words_clean():
    assert BannedWordsConstraint(["foo", "bar"]).check("hello world").passed


def test_banned_words_hit():
    r = BannedWordsConstraint(["secret"]).check("the SECRET is out")
    assert not r.passed
    assert "secret" in r.message


def test_banned_words_case_sensitive():
    assert BannedWordsConstraint(["X"], case_sensitive=True).check("lowercase x").passed


# ── Constraints: Predicate ────────────────────────────────────────────────────

def test_predicate_pass():
    c = PredicateConstraint(lambda s: s.startswith("OK"), name="starts_ok")
    assert c.check("OK done").passed


def test_predicate_fail():
    c = PredicateConstraint(lambda s: False, message="nope")
    r = c.check("anything")
    assert not r.passed
    assert r.message == "nope"


def test_predicate_exception_handled():
    c = PredicateConstraint(lambda s: 1 / 0)
    r = c.check("x")
    assert not r.passed
    assert "error" in r.message.lower()


# ── Validator construction ────────────────────────────────────────────────────

def test_invalid_max_retries_raises():
    with pytest.raises(ValueError):
        OutputValidator(max_retries=-1)


def test_add_and_list_constraints():
    v = OutputValidator()
    v.add_constraint(NonEmptyConstraint())
    v.add_constraint(JSONConstraint())
    assert v.list_constraints() == ["non_empty", "json"]


def test_validate_returns_all_results():
    v = OutputValidator([NonEmptyConstraint(), LengthConstraint(min_len=100)])
    results = v.validate("short")
    assert len(results) == 2
    assert results[0].passed is True
    assert results[1].passed is False


# ── Repair loop ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_first_pass_success():
    v = OutputValidator([JSONConstraint()], max_retries=2)
    result = await v.validate_and_repair([{"role": "user", "content": "go"}], _const('{"a":1}'))
    assert result.valid is True
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_repair_succeeds_on_retry():
    # first response bad JSON, second good
    inv = _sequence("not json", '{"ok":true}')
    v = OutputValidator([JSONConstraint()], max_retries=2)
    result = await v.validate_and_repair([{"role": "user", "content": "go"}], inv)
    assert result.valid is True
    assert result.attempts == 2


@pytest.mark.asyncio
async def test_repair_exhausts_retries():
    v = OutputValidator([JSONConstraint()], max_retries=2)
    result = await v.validate_and_repair([{"role": "user", "content": "go"}], _const("never json"))
    assert result.valid is False
    assert result.attempts == 3  # 1 initial + 2 retries
    assert len(result.failures) == 1


@pytest.mark.asyncio
async def test_zero_retries_single_attempt():
    v = OutputValidator([JSONConstraint()], max_retries=0)
    result = await v.validate_and_repair([{"role": "user", "content": "go"}], _const("bad"))
    assert result.valid is False
    assert result.attempts == 1


@pytest.mark.asyncio
async def test_feedback_appended_to_conversation():
    seen_lengths = []

    async def _inv(messages):
        seen_lengths.append(len(messages))
        return "bad"

    v = OutputValidator([JSONConstraint()], max_retries=1)
    await v.validate_and_repair([{"role": "user", "content": "go"}], _inv)
    # first call: 1 message; second call: 1 + assistant + feedback = 3
    assert seen_lengths == [1, 3]


@pytest.mark.asyncio
async def test_multiple_constraints_all_must_pass():
    v = OutputValidator(
        [NonEmptyConstraint(), LengthConstraint(min_len=3), BannedWordsConstraint(["bad"])],
        max_retries=0,
    )
    result = await v.validate_and_repair([{"role": "user", "content": "go"}], _const("ok good"))
    assert result.valid is True


# ── ValidationResult shape ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_result_to_dict_shape():
    v = OutputValidator([JSONConstraint()], max_retries=0)
    result = await v.validate_and_repair([{"role": "user", "content": "go"}], _const("bad"))
    d = result.to_dict()
    for key in ("valid", "response", "attempts", "constraint_results", "failures", "duration_ms"):
        assert key in d


@pytest.mark.asyncio
async def test_result_failures_property():
    v = OutputValidator([NonEmptyConstraint(), JSONConstraint()], max_retries=0)
    result = await v.validate_and_repair([{"role": "user", "content": "go"}], _const("plain text"))
    # non_empty passes, json fails
    assert len(result.failures) == 1
    assert result.failures[0].name == "json"


# ── Metrics ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_metrics_first_pass():
    v = OutputValidator([NonEmptyConstraint()], max_retries=1)
    await v.validate_and_repair([{"role": "user", "content": "go"}], _const("hi"))
    m = v.metrics()
    assert m["total_validations"] == 1
    assert m["first_pass_successes"] == 1
    assert m["success_rate"] == 1.0


@pytest.mark.asyncio
async def test_metrics_repaired():
    inv = _sequence("", "fixed")
    v = OutputValidator([NonEmptyConstraint()], max_retries=2)
    await v.validate_and_repair([{"role": "user", "content": "go"}], inv)
    m = v.metrics()
    assert m["repaired_successes"] == 1
    assert m["repair_rate"] == 1.0


@pytest.mark.asyncio
async def test_metrics_failure():
    v = OutputValidator([JSONConstraint()], max_retries=0)
    await v.validate_and_repair([{"role": "user", "content": "go"}], _const("bad"))
    m = v.metrics()
    assert m["failures"] == 1
    assert m["success_rate"] == 0.0


@pytest.mark.asyncio
async def test_metrics_reset():
    v = OutputValidator([JSONConstraint()], max_retries=0)
    await v.validate_and_repair([{"role": "user", "content": "go"}], _const("bad"))
    v.reset_metrics()
    m = v.metrics()
    assert m["total_validations"] == 0
    assert m["failures"] == 0


@pytest.mark.asyncio
async def test_metrics_shape():
    v = OutputValidator([JSONConstraint()])
    m = v.metrics()
    for key in ("total_validations", "first_pass_successes", "repaired_successes",
                "failures", "success_rate", "repair_rate", "constraint_count"):
        assert key in m


# ── Thread safety ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_concurrent_validations():
    v = OutputValidator([NonEmptyConstraint()], max_retries=0)

    async def run_once():
        await v.validate_and_repair([{"role": "user", "content": "go"}], _const("ok"))

    await asyncio.gather(*[run_once() for _ in range(15)])
    assert v.metrics()["total_validations"] == 15
