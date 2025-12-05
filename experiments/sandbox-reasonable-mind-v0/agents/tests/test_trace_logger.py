from agents.core.trace_logger import TraceLogger


def test_trace_logger_keeps_bounded_events():
    logger = TraceLogger(keep_last=2)
    logger.log("a", {"x": 1})
    logger.log("b", {"x": 2})
    logger.log("c", {"x": 3})

    events = logger.get_events()
    assert len(events) == 2
    assert events[0]["type"] == "b"
    assert events[1]["type"] == "c"
