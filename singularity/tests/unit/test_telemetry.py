"""Unit testy telemetrie — nesmí spadnout ani bez prometheus_client."""
from __future__ import annotations

import pytest

from core import telemetry

pytestmark = pytest.mark.unit


def test_record_request_does_not_raise():
    telemetry.record_request("claude", "kritik", "ok", 0.123)


def test_record_switch_does_not_raise():
    telemetry.record_switch("claude", "gemini")


def test_record_cooldown_does_not_raise():
    telemetry.record_cooldown("gemini")


def test_metrics_payload_returns_bytes():
    payload, content_type = telemetry.metrics_payload()
    assert isinstance(payload, bytes)
    assert isinstance(content_type, str)
