"""
Unit tests — Webhook Dispatcher (Fáze 55). Fully offline, deterministic.

send_fn is mocked; no real HTTP. sleep_fn is a no-op so retries are instant.
"""

from __future__ import annotations

import json
import pytest

from core.webhook_dispatcher import (
    DeadLetter,
    DeliveryResult,
    DeliveryStatus,
    Subscription,
    WebhookDispatcher,
    sign_payload,
)


async def _noop_sleep(_seconds):
    return None


def _ok_sender(code: int = 200):
    captured = []

    async def _send(url, payload, headers):
        captured.append({"url": url, "payload": payload, "headers": headers})
        return code
    _send.captured = captured
    return _send


def _seq_sender(*codes):
    """Returns the next code each call; raises if code is None."""
    state = {"i": 0}

    async def _send(url, payload, headers):
        c = codes[min(state["i"], len(codes) - 1)]
        state["i"] += 1
        if c is None:
            raise RuntimeError("connection error")
        return c
    return _send


def _dispatcher(**kw):
    kw.setdefault("sleep_fn", _noop_sleep)
    kw.setdefault("backoff_base", 0.0)
    return WebhookDispatcher(**kw)


# ── Signing ──────────────────────────────────────────────────────────────────────

def test_sign_payload_deterministic():
    assert sign_payload("secret", "body") == sign_payload("secret", "body")


def test_sign_payload_differs_by_secret():
    assert sign_payload("a", "body") != sign_payload("b", "body")


def test_sign_payload_hex_length():
    # SHA256 hex = 64 chars
    assert len(sign_payload("s", "x")) == 64


# ── Construction ─────────────────────────────────────────────────────────────────

def test_invalid_max_retries_raises():
    with pytest.raises(ValueError):
        WebhookDispatcher(max_retries=-1)


def test_invalid_backoff_raises():
    with pytest.raises(ValueError):
        WebhookDispatcher(backoff_base=-1)


# ── Subscription management ──────────────────────────────────────────────────────

def test_subscribe_returns_id():
    d = _dispatcher()
    sid = d.subscribe("https://x.com/hook", "secret")
    assert sid
    assert len(d.list_subscriptions()) == 1


def test_subscribe_requires_url_and_secret():
    d = _dispatcher()
    with pytest.raises(ValueError):
        d.subscribe("", "secret")
    with pytest.raises(ValueError):
        d.subscribe("https://x.com", "")


def test_unsubscribe():
    d = _dispatcher()
    sid = d.subscribe("https://x.com", "s")
    assert d.unsubscribe(sid) is True
    assert d.list_subscriptions() == []


def test_unsubscribe_missing():
    d = _dispatcher()
    assert d.unsubscribe("nope") is False


def test_set_active():
    d = _dispatcher()
    sid = d.subscribe("https://x.com", "s")
    assert d.set_active(sid, False) is True
    subs = d.list_subscriptions()
    assert subs[0]["active"] is False


# ── Dispatch: delivery ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_no_subscribers():
    d = _dispatcher()
    r = await d.dispatch("evt", {"a": 1}, _ok_sender())
    assert r.status == DeliveryStatus.NO_SUBSCRIBERS.value
    assert r.delivered == 0


@pytest.mark.asyncio
async def test_dispatch_delivers():
    d = _dispatcher()
    d.subscribe("https://x.com/hook", "secret")
    sender = _ok_sender(200)
    r = await d.dispatch("evt", {"a": 1}, sender)
    assert r.status == DeliveryStatus.DELIVERED.value
    assert r.delivered == 1
    assert r.failed == 0
    assert len(sender.captured) == 1


@pytest.mark.asyncio
async def test_dispatch_includes_signature_header():
    d = _dispatcher()
    d.subscribe("https://x.com/hook", "mysecret")
    sender = _ok_sender(200)
    await d.dispatch("evt", {"a": 1}, sender)
    headers = sender.captured[0]["headers"]
    assert "X-Singularity-Signature" in headers
    # signature must verify against the delivered payload
    payload = sender.captured[0]["payload"]
    assert headers["X-Singularity-Signature"] == sign_payload("mysecret", payload)


@pytest.mark.asyncio
async def test_payload_envelope_shape():
    d = _dispatcher()
    d.subscribe("https://x.com", "s")
    sender = _ok_sender(200)
    await d.dispatch("user.created", {"id": 7}, sender)
    env = json.loads(sender.captured[0]["payload"])
    assert env["event_type"] == "user.created"
    assert env["data"] == {"id": 7}
    assert "event_id" in env


# ── Event filtering ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_event_filter_matches():
    d = _dispatcher()
    d.subscribe("https://x.com", "s", events=["order.paid"])
    sender = _ok_sender(200)
    r = await d.dispatch("order.paid", {}, sender)
    assert r.delivered == 1


@pytest.mark.asyncio
async def test_event_filter_excludes():
    d = _dispatcher()
    d.subscribe("https://x.com", "s", events=["order.paid"])
    sender = _ok_sender(200)
    r = await d.dispatch("order.refunded", {}, sender)
    assert r.status == DeliveryStatus.NO_SUBSCRIBERS.value


@pytest.mark.asyncio
async def test_empty_events_matches_all():
    d = _dispatcher()
    d.subscribe("https://x.com", "s")  # no filter
    r = await d.dispatch("anything", {}, _ok_sender(200))
    assert r.delivered == 1


@pytest.mark.asyncio
async def test_inactive_not_delivered():
    d = _dispatcher()
    sid = d.subscribe("https://x.com", "s")
    d.set_active(sid, False)
    r = await d.dispatch("evt", {}, _ok_sender(200))
    assert r.status == DeliveryStatus.NO_SUBSCRIBERS.value


# ── Retry & dead-letter ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retry_then_success():
    d = _dispatcher(max_retries=3)
    d.subscribe("https://x.com", "s")
    # fail twice (500), then 200
    r = await d.dispatch("evt", {}, _seq_sender(500, 500, 200))
    assert r.delivered == 1
    assert r.attempts[0]["tries"] == 3


@pytest.mark.asyncio
async def test_exhausted_retries_dead_letters():
    d = _dispatcher(max_retries=2)
    d.subscribe("https://x.com", "s")
    r = await d.dispatch("evt", {}, _ok_sender(500))
    assert r.status == DeliveryStatus.FAILED.value
    assert r.failed == 1
    dls = d.dead_letters()
    assert len(dls) == 1
    assert dls[0]["last_code"] == 500
    assert dls[0]["tries"] == 3  # 1 + 2 retries


@pytest.mark.asyncio
async def test_exception_treated_as_failure():
    d = _dispatcher(max_retries=1)
    d.subscribe("https://x.com", "s")
    r = await d.dispatch("evt", {}, _seq_sender(None, None))
    assert r.failed == 1
    assert d.dead_letters()[0]["last_code"] is None


@pytest.mark.asyncio
async def test_clear_dead_letters():
    d = _dispatcher(max_retries=0)
    d.subscribe("https://x.com", "s")
    await d.dispatch("evt", {}, _ok_sender(500))
    assert d.clear_dead_letters() == 1
    assert d.dead_letters() == []


@pytest.mark.asyncio
async def test_dead_letter_capacity_bounded():
    d = _dispatcher(max_retries=0, max_dead_letters=3)
    d.subscribe("https://x.com", "s")
    for _ in range(5):
        await d.dispatch("evt", {}, _ok_sender(500))
    assert len(d.dead_letters()) == 3


# ── Multiple subscribers ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_partial_failure_across_subscribers():
    d = _dispatcher(max_retries=0)
    d.subscribe("https://ok.com", "s", sub_id="ok")
    d.subscribe("https://bad.com", "s", sub_id="bad")

    async def _send(url, payload, headers):
        return 200 if "ok.com" in url else 500

    r = await d.dispatch("evt", {}, _send)
    assert r.delivered == 1
    assert r.failed == 1
    assert r.status == DeliveryStatus.FAILED.value


# ── Result shape ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_result_to_dict_shape():
    d = _dispatcher()
    d.subscribe("https://x.com", "s")
    r = await d.dispatch("evt", {}, _ok_sender(200))
    dd = r.to_dict()
    for key in ("event_id", "event_type", "attempts", "delivered", "failed", "status"):
        assert key in dd


# ── Metrics ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_metrics_accumulate():
    d = _dispatcher(max_retries=0)
    d.subscribe("https://x.com", "s")
    await d.dispatch("evt", {}, _ok_sender(200))
    await d.dispatch("evt", {}, _ok_sender(500))
    m = d.metrics()
    assert m["total_events"] == 2
    assert m["total_delivered"] == 1
    assert m["total_failed"] == 1
    assert m["delivery_rate"] == 0.5


@pytest.mark.asyncio
async def test_metrics_reset():
    d = _dispatcher(max_retries=0)
    d.subscribe("https://x.com", "s")
    await d.dispatch("evt", {}, _ok_sender(200))
    d.reset_metrics()
    m = d.metrics()
    assert m["total_events"] == 0
    assert m["total_delivered"] == 0


def test_metrics_shape():
    d = _dispatcher()
    m = d.metrics()
    for key in ("total_events", "total_delivered", "total_failed",
                "total_attempts", "subscriptions", "dead_letters", "delivery_rate"):
        assert key in m
