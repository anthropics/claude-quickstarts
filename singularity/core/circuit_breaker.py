"""
Singularity — Circuit Breaker (Fáze 25).

Classic three-state resilience pattern per named resource.

  CLOSED  — normal; count failures toward failure_threshold
  OPEN    — reject calls immediately; start recovery_timeout_s timer
  HALF_OPEN — let one probe through; success → CLOSED, failure → OPEN

Thread-safe; no external dependencies.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

import structlog

log = structlog.get_logger()


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int      # failures in CLOSED before opening
    recovery_timeout_s: float   # seconds in OPEN before probing
    success_threshold: int      # successes in HALF_OPEN before closing

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    opened_at: float | None = None          # monotonic
    last_failure_at: str | None = None
    last_state_change_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    total_failures: int = 0
    total_successes: int = 0
    total_rejected: int = 0

    def is_open(self) -> bool:
        """Returns True when the breaker should reject the call."""
        if self.state == CircuitState.CLOSED:
            return False
        if self.state == CircuitState.OPEN:
            if self.opened_at and (time.monotonic() - self.opened_at) >= self.recovery_timeout_s:
                self._transition(CircuitState.HALF_OPEN)
                return False   # let the probe through
            return True
        # HALF_OPEN: allow one probe
        return False

    def record_success(self) -> None:
        self.total_successes += 1
        if self.state == CircuitState.CLOSED:
            self.failure_count = 0
        elif self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self._transition(CircuitState.CLOSED)
        # if somehow called while OPEN, do nothing

    def record_failure(self) -> None:
        self.total_failures += 1
        self.last_failure_at = datetime.now(timezone.utc).isoformat()
        if self.state == CircuitState.CLOSED:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self._transition(CircuitState.OPEN)
        elif self.state == CircuitState.HALF_OPEN:
            self._transition(CircuitState.OPEN)

    def record_rejected(self) -> None:
        self.total_rejected += 1

    def reset(self) -> None:
        self._transition(CircuitState.CLOSED)

    def _transition(self, new_state: CircuitState) -> None:
        old_state = self.state
        self.state = new_state
        self.last_state_change_at = datetime.now(timezone.utc).isoformat()
        self.failure_count = 0
        self.success_count = 0
        if new_state == CircuitState.OPEN:
            self.opened_at = time.monotonic()
        else:
            self.opened_at = None
        log.info("circuit_breaker_transition", name=self.name,
                 from_state=old_state.value, to_state=new_state.value)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_s": self.recovery_timeout_s,
            "success_threshold": self.success_threshold,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_at": self.last_failure_at,
            "last_state_change_at": self.last_state_change_at,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "total_rejected": self.total_rejected,
        }


class CircuitBreakerRegistry:
    """
    Thread-safe registry of named circuit breakers.

    Usage:
        if reg.is_open("gemini"):
            raise RuntimeError("Circuit open — gemini unavailable")
        try:
            result = await call_gemini(...)
            reg.record_success("gemini")
        except Exception:
            reg.record_failure("gemini")
            raise
    """

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get_or_create(
        self,
        name: str,
        *,
        failure_threshold: int = 5,
        recovery_timeout_s: float = 60.0,
        success_threshold: int = 2,
    ) -> CircuitBreaker:
        if not name or not name.strip():
            raise ValueError("name must not be empty")
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if recovery_timeout_s <= 0:
            raise ValueError("recovery_timeout_s must be positive")
        if success_threshold < 1:
            raise ValueError("success_threshold must be >= 1")
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(
                    name=name,
                    failure_threshold=failure_threshold,
                    recovery_timeout_s=recovery_timeout_s,
                    success_threshold=success_threshold,
                )
            return self._breakers[name]

    def is_open(self, name: str) -> bool:
        with self._lock:
            cb = self._breakers.get(name)
        if cb is None:
            return False
        with self._lock:
            return cb.is_open()

    def record_success(self, name: str) -> None:
        with self._lock:
            cb = self._breakers.get(name)
            if cb:
                cb.record_success()

    def record_failure(self, name: str) -> None:
        with self._lock:
            cb = self._breakers.get(name)
            if cb:
                cb.record_failure()

    def record_rejected(self, name: str) -> None:
        with self._lock:
            cb = self._breakers.get(name)
            if cb:
                cb.record_rejected()

    def reset(self, name: str) -> bool:
        with self._lock:
            cb = self._breakers.get(name)
            if cb is None:
                return False
            cb.reset()
        return True

    def get_state(self, name: str) -> dict | None:
        with self._lock:
            cb = self._breakers.get(name)
        return cb.to_dict() if cb else None

    def list_breakers(self) -> list[dict]:
        with self._lock:
            items = list(self._breakers.values())
        return [cb.to_dict() for cb in items]

    def breaker_count(self) -> int:
        with self._lock:
            return len(self._breakers)
