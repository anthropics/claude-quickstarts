"""
Singularity — Webhook Dispatcher (Fáze 55).

Outbound event delivery to registered subscriber endpoints. Each event is
serialized to JSON, signed with a per-subscriber HMAC-SHA256 secret, and
delivered with bounded retry + exponential backoff; permanently failed
deliveries land in a dead-letter queue for inspection/replay.

The HTTP transport is an injectable async ``send_fn`` so the module is fully
offline-testable — production wires it to an httpx client. Dependency-free
core (stdlib hashlib/hmac/json).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable


class DeliveryStatus(str, Enum):
    DELIVERED = "delivered"
    FAILED = "failed"        # exhausted retries → dead-letter
    NO_SUBSCRIBERS = "no_subscribers"


# send_fn(url, payload_json, headers) -> status_code (2xx = success)
SendFn = Callable[[str, str, dict], Awaitable[int]]


# ── Data structures ─────────────────────────────────────────────────────────────

@dataclass
class Subscription:
    sub_id: str
    url: str
    secret: str
    events: set[str] = field(default_factory=set)   # empty = all events
    active: bool = True

    def to_dict(self) -> dict:
        return {
            "sub_id": self.sub_id,
            "url": self.url,
            "events": sorted(self.events),
            "active": self.active,
        }


@dataclass
class DeliveryResult:
    event_id: str
    event_type: str
    attempts: list[dict] = field(default_factory=list)  # [{sub_id, status, code, tries}]
    delivered: int = 0
    failed: int = 0
    status: str = DeliveryStatus.NO_SUBSCRIBERS.value

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "attempts": self.attempts,
            "delivered": self.delivered,
            "failed": self.failed,
            "status": self.status,
        }


@dataclass
class DeadLetter:
    event_id: str
    event_type: str
    sub_id: str
    url: str
    payload: str
    last_code: int | None
    tries: int


def sign_payload(secret: str, payload: str) -> str:
    """HMAC-SHA256 hex signature of a payload string."""
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


# ── Dispatcher ──────────────────────────────────────────────────────────────────

class WebhookDispatcher:
    """
    Register subscribers, then ``dispatch`` events to all that match.

    ``max_retries`` retry attempts per subscriber on non-2xx / exception;
    ``backoff_base`` seconds grows exponentially. A ``sleep_fn`` is injectable
    so tests run instantly.
    """

    def __init__(
        self,
        *,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        max_dead_letters: int = 100,
        sleep_fn: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if backoff_base < 0:
            raise ValueError("backoff_base must be >= 0")
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.max_dead_letters = max_dead_letters
        self._sleep_fn = sleep_fn
        self._lock = threading.Lock()

        self._subs: dict[str, Subscription] = {}
        self._dead_letters: list[DeadLetter] = []

        # metrics
        self._total_events = 0
        self._total_delivered = 0
        self._total_failed = 0
        self._total_attempts = 0

    # ── Subscription management ────────────────────────────────────────────────────

    def subscribe(
        self, url: str, secret: str, *, events: list[str] | None = None,
        sub_id: str | None = None,
    ) -> str:
        if not url:
            raise ValueError("url is required")
        if not secret:
            raise ValueError("secret is required")
        sid = sub_id or f"sub_{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._subs[sid] = Subscription(
                sub_id=sid, url=url, secret=secret,
                events=set(events or []),
            )
        return sid

    def unsubscribe(self, sub_id: str) -> bool:
        with self._lock:
            return self._subs.pop(sub_id, None) is not None

    def set_active(self, sub_id: str, active: bool) -> bool:
        with self._lock:
            sub = self._subs.get(sub_id)
            if sub is None:
                return False
            sub.active = active
            return True

    def list_subscriptions(self) -> list[dict]:
        with self._lock:
            return [s.to_dict() for s in self._subs.values()]

    def _matching(self, event_type: str) -> list[Subscription]:
        return [
            s for s in self._subs.values()
            if s.active and (not s.events or event_type in s.events)
        ]

    # ── Dispatch ────────────────────────────────────────────────────────────────

    async def dispatch(
        self, event_type: str, data: dict, send_fn: SendFn,
    ) -> DeliveryResult:
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        with self._lock:
            targets = self._matching(event_type)
            self._total_events += 1

        result = DeliveryResult(event_id=event_id, event_type=event_type)
        if not targets:
            result.status = DeliveryStatus.NO_SUBSCRIBERS.value
            return result

        envelope = {"event_id": event_id, "event_type": event_type, "data": data}
        payload = json.dumps(envelope, sort_keys=True)

        for sub in targets:
            code, tries, ok = await self._deliver_with_retry(sub, payload, send_fn)
            with self._lock:
                self._total_attempts += tries
            attempt = {"sub_id": sub.sub_id, "code": code, "tries": tries,
                       "status": "delivered" if ok else "failed"}
            result.attempts.append(attempt)
            if ok:
                result.delivered += 1
                with self._lock:
                    self._total_delivered += 1
            else:
                result.failed += 1
                with self._lock:
                    self._total_failed += 1
                    self._add_dead_letter(DeadLetter(
                        event_id=event_id, event_type=event_type, sub_id=sub.sub_id,
                        url=sub.url, payload=payload, last_code=code, tries=tries,
                    ))

        result.status = (
            DeliveryStatus.DELIVERED.value if result.failed == 0
            else DeliveryStatus.FAILED.value
        )
        return result

    async def _deliver_with_retry(
        self, sub: Subscription, payload: str, send_fn: SendFn,
    ) -> tuple[int | None, int, bool]:
        headers = {
            "Content-Type": "application/json",
            "X-Singularity-Signature": sign_payload(sub.secret, payload),
        }
        last_code: int | None = None
        for attempt in range(self.max_retries + 1):
            tries = attempt + 1
            try:
                code = await send_fn(sub.url, payload, headers)
                last_code = code
                if 200 <= code < 300:
                    return code, tries, True
            except Exception:
                last_code = None
            if attempt < self.max_retries and self._sleep_fn is not None:
                await self._sleep_fn(self.backoff_base * (2 ** attempt))
        return last_code, self.max_retries + 1, False

    # ── Dead-letter queue ─────────────────────────────────────────────────────────

    def _add_dead_letter(self, dl: DeadLetter) -> None:
        self._dead_letters.append(dl)
        if len(self._dead_letters) > self.max_dead_letters:
            self._dead_letters.pop(0)

    def dead_letters(self) -> list[dict]:
        with self._lock:
            return [
                {"event_id": d.event_id, "event_type": d.event_type,
                 "sub_id": d.sub_id, "url": d.url, "last_code": d.last_code,
                 "tries": d.tries}
                for d in self._dead_letters
            ]

    def clear_dead_letters(self) -> int:
        with self._lock:
            n = len(self._dead_letters)
            self._dead_letters.clear()
            return n

    # ── Metrics ───────────────────────────────────────────────────────────────────

    def metrics(self) -> dict:
        with self._lock:
            return {
                "total_events": self._total_events,
                "total_delivered": self._total_delivered,
                "total_failed": self._total_failed,
                "total_attempts": self._total_attempts,
                "subscriptions": len(self._subs),
                "dead_letters": len(self._dead_letters),
                "delivery_rate": round(
                    self._total_delivered
                    / (self._total_delivered + self._total_failed), 4
                ) if (self._total_delivered + self._total_failed) else 0.0,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total_events = 0
            self._total_delivered = 0
            self._total_failed = 0
            self._total_attempts = 0
