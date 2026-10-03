"""
Singularity — Threshold-based Alerting System (Fáze 20).

Defines named alerts tied to a condition + threshold. When evaluate() is
called with the current metric value, any active alert whose threshold is
crossed fires an HTTP POST to its callback_url.

No external state — fully offline-testable by mocking httpx.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

import structlog

log = structlog.get_logger()


class AlertCondition(str, Enum):
    BUDGET_EXCEEDED = "budget_exceeded"         # value = cumulative spend USD
    ERROR_RATE_HIGH = "error_rate_high"         # value = failure fraction 0.0–1.0
    LATENCY_HIGH = "latency_high"               # value = avg latency ms
    PROVIDER_COOLDOWN = "provider_cooldown"     # value = consecutive_failures count
    QUEUE_DEPTH_HIGH = "queue_depth_high"       # value = pending task count
    FEEDBACK_RATING_LOW = "feedback_rating_low" # value = avg rating (1–5); fires when LOW


@dataclass
class Alert:
    alert_id: str
    name: str
    condition: AlertCondition
    threshold: float
    callback_url: str
    status: str = "active"         # "active" | "muted"
    fire_count: int = 0
    last_fired_at: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def is_triggered(self, value: float) -> bool:
        if self.condition == AlertCondition.FEEDBACK_RATING_LOW:
            return value <= self.threshold  # low rating: fire when AT OR BELOW threshold
        return value >= self.threshold      # all others: fire when AT OR ABOVE threshold

    def to_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "name": self.name,
            "condition": self.condition.value,
            "threshold": self.threshold,
            "callback_url": self.callback_url,
            "status": self.status,
            "fire_count": self.fire_count,
            "last_fired_at": self.last_fired_at,
            "created_at": self.created_at,
        }


_VALID_STATUSES = frozenset({"active", "muted"})


class AlertManager:
    """
    Thread-safe manager for threshold-based alerts.

    Usage:
        aid = mgr.create_alert("budget-warn", "budget_exceeded", 10.0, "https://...")
        fired = await mgr.evaluate("budget_exceeded", current_spend)
    """

    def __init__(self) -> None:
        self._alerts: dict[str, Alert] = {}
        self._lock = threading.Lock()

    def create_alert(
        self,
        name: str,
        condition: str,
        threshold: float,
        callback_url: str,
    ) -> str:
        try:
            cond = AlertCondition(condition)
        except ValueError:
            valid = [c.value for c in AlertCondition]
            raise ValueError(f"Unknown condition {condition!r}. Valid: {valid}")
        if not callback_url:
            raise ValueError("callback_url must not be empty")
        alert_id = str(uuid.uuid4())
        with self._lock:
            self._alerts[alert_id] = Alert(
                alert_id=alert_id,
                name=name,
                condition=cond,
                threshold=threshold,
                callback_url=callback_url,
            )
        log.info("alert_created", alert_id=alert_id, condition=condition, threshold=threshold)
        return alert_id

    def get_alert(self, alert_id: str) -> dict | None:
        with self._lock:
            a = self._alerts.get(alert_id)
        return a.to_dict() if a else None

    def list_alerts(self) -> list[dict]:
        with self._lock:
            items = list(self._alerts.values())
        return [a.to_dict() for a in items]

    def set_status(self, alert_id: str, status: str) -> bool:
        if status not in _VALID_STATUSES:
            raise ValueError(f"status must be 'active' or 'muted', got {status!r}")
        with self._lock:
            a = self._alerts.get(alert_id)
            if a is None:
                return False
            a.status = status
        return True

    def delete_alert(self, alert_id: str) -> bool:
        with self._lock:
            if alert_id not in self._alerts:
                return False
            del self._alerts[alert_id]
        return True

    def alert_count(self) -> int:
        with self._lock:
            return len(self._alerts)

    async def evaluate(self, condition: str, value: float) -> list[str]:
        """
        Evaluate all active alerts for this condition against value.
        Fires (HTTP POST) any whose threshold is crossed.
        Returns list of alert_ids that fired.
        """
        try:
            cond = AlertCondition(condition)
        except ValueError:
            return []

        with self._lock:
            candidates = [
                a for a in self._alerts.values()
                if a.condition == cond and a.status == "active"
            ]

        fired: list[str] = []
        for alert in candidates:
            if alert.is_triggered(value):
                await self._fire(alert, value)
                fired.append(alert.alert_id)
        return fired

    async def _fire(self, alert: Alert, value: float) -> None:
        fired_at = datetime.now(timezone.utc).isoformat()
        with self._lock:
            alert.fire_count += 1
            alert.last_fired_at = fired_at

        payload = {
            "alert_id": alert.alert_id,
            "name": alert.name,
            "condition": alert.condition.value,
            "threshold": alert.threshold,
            "value": value,
            "fired_at": fired_at,
        }
        log.warning("alert_fired", alert_id=alert.alert_id,
                    condition=alert.condition.value, threshold=alert.threshold, value=value)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(alert.callback_url, json=payload)
        except Exception as exc:
            log.error("alert_callback_failed", alert_id=alert.alert_id, error=str(exc))
