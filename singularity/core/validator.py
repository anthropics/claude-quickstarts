"""
Singularity — Output Validator (Fáze 31).

Validates LLM responses against composable constraints and runs a
retry-with-feedback repair loop: when a response fails validation, the
failure messages are fed back to the model so it can correct itself.

Fully provider-agnostic — the caller supplies an async ``invoke_fn`` so the
module is testable offline with deterministic mock responses.
"""

from __future__ import annotations

import json
import re
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


# ── Results ───────────────────────────────────────────────────────────────────

@dataclass
class ConstraintResult:
    name: str
    passed: bool
    message: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed, "message": self.message}


@dataclass
class ValidationResult:
    valid: bool
    response: str
    attempts: int
    constraint_results: list[ConstraintResult] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def failures(self) -> list[ConstraintResult]:
        return [c for c in self.constraint_results if not c.passed]

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "response": self.response,
            "attempts": self.attempts,
            "constraint_results": [c.to_dict() for c in self.constraint_results],
            "failures": [c.to_dict() for c in self.failures],
            "duration_ms": self.duration_ms,
        }


# ── Constraints ───────────────────────────────────────────────────────────────

class Constraint(ABC):
    """Base class. Subclasses check a response and return a ConstraintResult."""

    name: str = "constraint"

    @abstractmethod
    def check(self, response: str) -> ConstraintResult: ...


class NonEmptyConstraint(Constraint):
    name = "non_empty"

    def check(self, response: str) -> ConstraintResult:
        ok = bool(response and response.strip())
        return ConstraintResult(self.name, ok, "" if ok else "Response is empty")


class JSONConstraint(Constraint):
    """Response must be valid JSON. Optionally require specific top-level keys."""

    name = "json"

    def __init__(self, required_keys: list[str] | None = None) -> None:
        self.required_keys = required_keys or []

    def check(self, response: str) -> ConstraintResult:
        try:
            parsed = json.loads(response)
        except (ValueError, TypeError) as exc:
            return ConstraintResult(self.name, False, f"Invalid JSON: {exc}")
        if self.required_keys:
            if not isinstance(parsed, dict):
                return ConstraintResult(
                    self.name, False, "JSON must be an object to check keys"
                )
            missing = [k for k in self.required_keys if k not in parsed]
            if missing:
                return ConstraintResult(
                    self.name, False, f"Missing required keys: {missing}"
                )
        return ConstraintResult(self.name, True)


class LengthConstraint(Constraint):
    name = "length"

    def __init__(self, min_len: int = 0, max_len: int | None = None) -> None:
        if min_len < 0:
            raise ValueError("min_len must be >= 0")
        if max_len is not None and max_len < min_len:
            raise ValueError("max_len must be >= min_len")
        self.min_len = min_len
        self.max_len = max_len

    def check(self, response: str) -> ConstraintResult:
        n = len(response)
        if n < self.min_len:
            return ConstraintResult(
                self.name, False, f"Too short: {n} < {self.min_len}"
            )
        if self.max_len is not None and n > self.max_len:
            return ConstraintResult(
                self.name, False, f"Too long: {n} > {self.max_len}"
            )
        return ConstraintResult(self.name, True)


class RegexConstraint(Constraint):
    name = "regex"

    def __init__(self, pattern: str, *, should_match: bool = True) -> None:
        self.pattern = re.compile(pattern)
        self.should_match = should_match

    def check(self, response: str) -> ConstraintResult:
        found = self.pattern.search(response) is not None
        if found == self.should_match:
            return ConstraintResult(self.name, True)
        verb = "must match" if self.should_match else "must not match"
        return ConstraintResult(
            self.name, False, f"Response {verb} pattern /{self.pattern.pattern}/"
        )


class BannedWordsConstraint(Constraint):
    name = "banned_words"

    def __init__(self, words: list[str], *, case_sensitive: bool = False) -> None:
        self.case_sensitive = case_sensitive
        self.words = words if case_sensitive else [w.lower() for w in words]

    def check(self, response: str) -> ConstraintResult:
        haystack = response if self.case_sensitive else response.lower()
        hits = [w for w in self.words if w in haystack]
        if hits:
            return ConstraintResult(
                self.name, False, f"Contains banned words: {hits}"
            )
        return ConstraintResult(self.name, True)


class PredicateConstraint(Constraint):
    """Wrap an arbitrary callable returning bool."""

    def __init__(
        self, predicate: Callable[[str], bool], *, name: str = "predicate",
        message: str = "Predicate failed",
    ) -> None:
        self._predicate = predicate
        self.name = name
        self._message = message

    def check(self, response: str) -> ConstraintResult:
        try:
            ok = bool(self._predicate(response))
        except Exception as exc:
            return ConstraintResult(self.name, False, f"Predicate error: {exc}")
        return ConstraintResult(self.name, ok, "" if ok else self._message)


# ── Validator ─────────────────────────────────────────────────────────────────

InvokeFn = Callable[[list[dict]], Awaitable[str]]


class OutputValidator:
    """
    Runs constraints against an LLM response and, on failure, retries by
    appending the validation feedback to the message list.

    Usage:
        validator = OutputValidator([JSONConstraint(["answer"])], max_retries=2)
        result = await validator.validate_and_repair(messages, invoke_fn)
    """

    def __init__(
        self,
        constraints: list[Constraint] | None = None,
        *,
        max_retries: int = 2,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        self._constraints: list[Constraint] = list(constraints or [])
        self.max_retries = max_retries
        self._lock = threading.Lock()

        # metrics
        self._total_validations = 0
        self._first_pass_successes = 0
        self._repaired_successes = 0
        self._failures = 0
        self._total_attempts = 0

    # ── Constraint management ─────────────────────────────────────────────────

    def add_constraint(self, constraint: Constraint) -> None:
        with self._lock:
            self._constraints.append(constraint)

    def list_constraints(self) -> list[str]:
        with self._lock:
            return [c.name for c in self._constraints]

    # ── Pure validation (no LLM) ──────────────────────────────────────────────

    def validate(self, response: str) -> list[ConstraintResult]:
        with self._lock:
            constraints = list(self._constraints)
        return [c.check(response) for c in constraints]

    @staticmethod
    def _all_passed(results: list[ConstraintResult]) -> bool:
        return all(r.passed for r in results)

    @staticmethod
    def _feedback(results: list[ConstraintResult]) -> str:
        fails = [r for r in results if not r.passed]
        lines = "\n".join(f"- {r.name}: {r.message}" for r in fails)
        return (
            "Your previous response failed these validation checks:\n"
            f"{lines}\n"
            "Please provide a corrected response that satisfies all checks."
        )

    # ── Repair loop ───────────────────────────────────────────────────────────

    async def validate_and_repair(
        self,
        messages: list[dict],
        invoke_fn: InvokeFn,
    ) -> ValidationResult:
        t0 = time.monotonic()
        convo = list(messages)
        attempts = 0
        results: list[ConstraintResult] = []
        response = ""

        # attempt 0 + up to max_retries repairs
        for attempt in range(self.max_retries + 1):
            attempts += 1
            response = await invoke_fn(convo)
            results = self.validate(response)
            if self._all_passed(results):
                self._record(attempt == 0, repaired=attempt > 0)
                return ValidationResult(
                    valid=True,
                    response=response,
                    attempts=attempts,
                    constraint_results=results,
                    duration_ms=(time.monotonic() - t0) * 1000,
                )
            # not last attempt → append feedback and retry
            if attempt < self.max_retries:
                convo = convo + [
                    {"role": "assistant", "content": response},
                    {"role": "user", "content": self._feedback(results)},
                ]

        self._record_failure(attempts)
        return ValidationResult(
            valid=False,
            response=response,
            attempts=attempts,
            constraint_results=results,
            duration_ms=(time.monotonic() - t0) * 1000,
        )

    # ── Metrics ───────────────────────────────────────────────────────────────

    def _record(self, first_pass: bool, *, repaired: bool) -> None:
        with self._lock:
            self._total_validations += 1
            if first_pass:
                self._first_pass_successes += 1
            elif repaired:
                self._repaired_successes += 1

    def _record_failure(self, attempts: int) -> None:
        with self._lock:
            self._total_validations += 1
            self._failures += 1
            self._total_attempts += attempts

    def metrics(self) -> dict:
        with self._lock:
            total = self._total_validations
            successes = self._first_pass_successes + self._repaired_successes
            return {
                "total_validations": total,
                "first_pass_successes": self._first_pass_successes,
                "repaired_successes": self._repaired_successes,
                "failures": self._failures,
                "success_rate": round(successes / total, 4) if total else 0.0,
                "repair_rate": round(self._repaired_successes / total, 4) if total else 0.0,
                "constraint_count": len(self._constraints),
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total_validations = 0
            self._first_pass_successes = 0
            self._repaired_successes = 0
            self._failures = 0
            self._total_attempts = 0
