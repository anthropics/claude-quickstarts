"""
Tests for LogBuffer and configure_logging (Fáze 10).
"""
import structlog
import pytest

from core.log_buffer import LogBuffer
from core.logging_config import configure_logging


@pytest.fixture(autouse=True)
def reset_structlog():
    """Restore structlog defaults after each test to avoid contaminating others."""
    yield
    structlog.reset_defaults()


def test_log_buffer_captures_events():
    buf = LogBuffer()
    configure_logging(level="DEBUG", log_format="console", log_buffer=buf)
    log = structlog.get_logger()
    log.info("test_event", key="value")
    assert len(buf) >= 1
    events = buf.get_recent()
    assert any(e.get("event") == "test_event" for e in events)


def test_log_buffer_respects_maxlen():
    buf = LogBuffer(maxlen=3)
    configure_logging(level="DEBUG", log_format="console", log_buffer=buf)
    log = structlog.get_logger()
    for i in range(10):
        log.info(f"msg_{i}")
    assert len(buf) == 3


def test_log_buffer_filter_by_level():
    buf = LogBuffer()
    configure_logging(level="DEBUG", log_format="console", log_buffer=buf)
    log = structlog.get_logger()
    log.info("info_event")
    log.warning("warn_event")
    warns = buf.get_recent(level="warning")
    assert all(e["_level"] == "warning" for e in warns)
    assert any(e.get("event") == "warn_event" for e in warns)


def test_log_buffer_get_recent_limit():
    buf = LogBuffer()
    configure_logging(level="DEBUG", log_format="console", log_buffer=buf)
    log = structlog.get_logger()
    for i in range(20):
        log.info(f"event_{i}")
    recent = buf.get_recent(limit=5)
    assert len(recent) == 5
    assert recent[-1].get("event") == "event_19"


def test_configure_logging_json_format_does_not_raise():
    buf = LogBuffer()
    configure_logging(level="INFO", log_format="json", log_buffer=buf)
    log = structlog.get_logger()
    log.info("json_test", answer=42)
    assert len(buf) >= 1


def test_log_buffer_clear():
    buf = LogBuffer()
    configure_logging(level="DEBUG", log_format="console", log_buffer=buf)
    log = structlog.get_logger()
    log.info("before_clear")
    assert len(buf) >= 1
    buf.clear()
    assert len(buf) == 0
