"""
Tests for OpenTelemetry tracing setup (Fáze 13).

The OTel SDK forbids resetting the global TracerProvider after the first call,
so we call setup_tracing() once per session and clear the in-memory exporter
before each test instead.
"""
import pytest

from core.tracing import clear_spans, get_finished_spans, get_tracer, setup_tracing


@pytest.fixture(scope="session", autouse=True)
def init_tracing():
    """Initialise in-memory tracing exactly once per test session."""
    setup_tracing(otlp_endpoint="", service_name="singularity-test")


@pytest.fixture(autouse=True)
def fresh_exporter():
    """Clear the in-memory exporter before every test."""
    clear_spans()
    yield
    clear_spans()


def test_get_tracer_returns_tracer():
    t = get_tracer("test")
    assert t is not None


def test_span_is_recorded():
    tracer = get_tracer("test")
    with tracer.start_as_current_span("test.span") as span:
        span.set_attribute("key", "value")
    spans = get_finished_spans()
    assert any(s["name"] == "test.span" for s in spans)


def test_span_has_attribute():
    tracer = get_tracer("test")
    with tracer.start_as_current_span("attr.span") as span:
        span.set_attribute("provider", "claude")
    spans = get_finished_spans()
    target = next(s for s in spans if s["name"] == "attr.span")
    assert target["attributes"].get("provider") == "claude"


def test_span_has_duration():
    tracer = get_tracer("test")
    with tracer.start_as_current_span("dur.span"):
        pass
    spans = get_finished_spans()
    target = next(s for s in spans if s["name"] == "dur.span")
    assert target["duration_ms"] is not None
    assert target["duration_ms"] >= 0


def test_clear_spans_empties_exporter():
    tracer = get_tracer("test")
    with tracer.start_as_current_span("clear.span"):
        pass
    assert len(get_finished_spans()) > 0
    clear_spans()
    assert get_finished_spans() == []


def test_get_finished_spans_respects_limit():
    tracer = get_tracer("test")
    for i in range(10):
        with tracer.start_as_current_span(f"span.{i}"):
            pass
    spans = get_finished_spans(limit=3)
    assert len(spans) == 3


def test_span_status_is_ok():
    tracer = get_tracer("test")
    with tracer.start_as_current_span("status.span"):
        pass
    spans = get_finished_spans()
    target = next(s for s in spans if s["name"] == "status.span")
    assert target["status"] == "UNSET"  # no explicit error set → UNSET


def test_multiple_spans_same_trace():
    tracer = get_tracer("test")
    with tracer.start_as_current_span("parent") as parent:
        with tracer.start_as_current_span("child"):
            pass
    spans = get_finished_spans()
    names = {s["name"] for s in spans}
    assert "parent" in names
    assert "child" in names
