"""
Singularity — Per-User Quota Manager (Fáze 24).

Tracks three metrics per user (requests, tokens, cost_usd) over rolling
time windows (hourly / daily / monthly). set_quota() defines a hard cap;
record_usage() accumulates usage; check_quota() tells callers whether the
user is still within their allowance.

No external state — fully offline.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Literal

import structlog

log = structlog.get_logger()

MetricName = Literal["requests", "tokens", "cost_usd"]
_METRICS: tuple[MetricName, ...] = ("requests", "tokens", "cost_usd")


class QuotaWindow(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"


def _window_start(window: QuotaWindow, now: datetime) -> datetime:
    """Return the start of the current window bucket."""
    if window == QuotaWindow.HOURLY:
        return now.replace(minute=0, second=0, microsecond=0)
    if window == QuotaWindow.DAILY:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    # MONTHLY
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _window_end(window: QuotaWindow, start: datetime) -> datetime:
    if window == QuotaWindow.HOURLY:
        return start + timedelta(hours=1)
    if window == QuotaWindow.DAILY:
        return start + timedelta(days=1)
    # MONTHLY — go to first day of next month
    if start.month == 12:
        return start.replace(year=start.year + 1, month=1)
    return start.replace(month=start.month + 1)


@dataclass
class QuotaRule:
    rule_id: str
    user_id: str
    metric: MetricName
    limit: float
    window: QuotaWindow
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "user_id": self.user_id,
            "metric": self.metric,
            "limit": self.limit,
            "window": self.window.value,
            "created_at": self.created_at,
        }


@dataclass
class _UsageBucket:
    """Accumulated usage within a single window bucket."""
    window_start: datetime
    requests: float = 0.0
    tokens: float = 0.0
    cost_usd: float = 0.0

    def get(self, metric: MetricName) -> float:
        return getattr(self, metric)

    def add(self, metric: MetricName, value: float) -> None:
        setattr(self, metric, getattr(self, metric) + value)


class QuotaManager:
    """
    Thread-safe per-user quota enforcement.

    Usage:
        mgr.set_quota("alice", "requests", limit=100, window="daily")
        mgr.record_usage("alice", requests=1, tokens=500)
        status = mgr.check_quota("alice", "requests")
        # {"allowed": True, "used": 1, "limit": 100, ...}
    """

    def __init__(self) -> None:
        self._rules: dict[str, QuotaRule] = {}
        self._buckets: dict[str, dict[QuotaWindow, _UsageBucket]] = {}
        self._lock = threading.Lock()

    # ── Quota rule CRUD ───────────────────────────────────────────────────────

    def set_quota(
        self,
        user_id: str,
        metric: MetricName,
        limit: float,
        window: str | QuotaWindow = QuotaWindow.DAILY,
    ) -> str:
        if not user_id or not user_id.strip():
            raise ValueError("user_id must not be empty")
        if metric not in _METRICS:
            raise ValueError(f"metric must be one of {_METRICS}, got {metric!r}")
        if limit <= 0:
            raise ValueError("limit must be positive")
        try:
            win = QuotaWindow(window) if isinstance(window, str) else window
        except ValueError:
            raise ValueError(f"window must be one of {[w.value for w in QuotaWindow]}")

        rule_id = str(uuid.uuid4())
        with self._lock:
            self._rules[rule_id] = QuotaRule(
                rule_id=rule_id,
                user_id=user_id,
                metric=metric,
                limit=limit,
                window=win,
            )
        log.info("quota_set", rule_id=rule_id, user_id=user_id,
                 metric=metric, limit=limit, window=win.value)
        return rule_id

    def get_quota(self, rule_id: str) -> dict | None:
        with self._lock:
            r = self._rules.get(rule_id)
        return r.to_dict() if r else None

    def list_quotas(self, user_id: str | None = None) -> list[dict]:
        with self._lock:
            items = list(self._rules.values())
        if user_id is not None:
            items = [r for r in items if r.user_id == user_id]
        return [r.to_dict() for r in items]

    def delete_quota(self, rule_id: str) -> bool:
        with self._lock:
            if rule_id not in self._rules:
                return False
            del self._rules[rule_id]
        return True

    def quota_count(self) -> int:
        with self._lock:
            return len(self._rules)

    # ── Usage tracking ────────────────────────────────────────────────────────

    def record_usage(
        self,
        user_id: str,
        *,
        requests: float = 0.0,
        tokens: float = 0.0,
        cost_usd: float = 0.0,
    ) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            if user_id not in self._buckets:
                self._buckets[user_id] = {}
            user_buckets = self._buckets[user_id]
            for win in QuotaWindow:
                start = _window_start(win, now)
                if win not in user_buckets or user_buckets[win].window_start < start:
                    user_buckets[win] = _UsageBucket(window_start=start)
                b = user_buckets[win]
                if requests:
                    b.add("requests", requests)
                if tokens:
                    b.add("tokens", tokens)
                if cost_usd:
                    b.add("cost_usd", cost_usd)

    def _get_usage(self, user_id: str, window: QuotaWindow) -> _UsageBucket:
        now = datetime.now(timezone.utc)
        start = _window_start(window, now)
        with self._lock:
            user_buckets = self._buckets.get(user_id, {})
            b = user_buckets.get(window)
            if b is None or b.window_start < start:
                return _UsageBucket(window_start=start)
            return b

    def check_quota(self, user_id: str, metric: MetricName) -> dict:
        """
        Return quota status for every rule matching (user_id, metric).
        If no rule exists, returns {"allowed": True, "rules": []}.
        A user is blocked only when at least one rule is exceeded.
        """
        now = datetime.now(timezone.utc)
        with self._lock:
            rules = [r for r in self._rules.values()
                     if r.user_id == user_id and r.metric == metric]

        if not rules:
            return {"allowed": True, "user_id": user_id, "metric": metric, "rules": []}

        rule_statuses = []
        allowed = True
        for rule in rules:
            b = self._get_usage(user_id, rule.window)
            used = b.get(metric)
            start = _window_start(rule.window, now)
            resets_at = _window_end(rule.window, start).isoformat()
            within = used < rule.limit
            if not within:
                allowed = False
            rule_statuses.append({
                "rule_id": rule.rule_id,
                "window": rule.window.value,
                "limit": rule.limit,
                "used": round(used, 6),
                "remaining": round(max(0.0, rule.limit - used), 6),
                "allowed": within,
                "resets_at": resets_at,
            })

        return {
            "allowed": allowed,
            "user_id": user_id,
            "metric": metric,
            "rules": rule_statuses,
        }

    def get_usage_summary(self, user_id: str) -> dict:
        """Return current usage across all windows for all three metrics."""
        summary: dict = {"user_id": user_id}
        for win in QuotaWindow:
            b = self._get_usage(user_id, win)
            summary[win.value] = {
                "requests": b.requests,
                "tokens": b.tokens,
                "cost_usd": round(b.cost_usd, 6),
            }
        return summary
