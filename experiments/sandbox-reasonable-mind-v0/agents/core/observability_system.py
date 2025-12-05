"""
Observability System - Phase 2

Implements:
- Token and step logging
- Latency counters and timing
- Structured event traces
- Metrics collection and export
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from contextlib import contextmanager
import time
import json
import threading


class EventType(Enum):
    """Types of observable events."""
    # Lifecycle events
    START = "start"
    END = "end"
    ERROR = "error"
    
    # Reasoning events
    REASONING_START = "reasoning_start"
    REASONING_STEP = "reasoning_step"
    REASONING_END = "reasoning_end"
    
    # Tool events
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOOL_ERROR = "tool_error"
    
    # Memory events
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    
    # Model events
    MODEL_REQUEST = "model_request"
    MODEL_RESPONSE = "model_response"
    TOKEN_COUNT = "token_count"
    
    # Custom
    CUSTOM = "custom"


class LogLevel(Enum):
    """Log levels for events."""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


@dataclass
class TraceEvent:
    """A single trace event."""
    event_id: str
    event_type: EventType
    timestamp: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    data: Dict[str, Any]
    duration_ms: Optional[float] = None
    level: LogLevel = LogLevel.INFO
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "type": self.event_type.value,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "data": self.data,
            "duration_ms": self.duration_ms,
            "level": self.level.name
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class Span:
    """A span representing a unit of work."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    start_time: float
    end_time: Optional[float] = None
    events: List[TraceEvent] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    status: str = "OK"
    
    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None
    
    def end(self) -> None:
        self.end_time = time.time()


@dataclass
class Trace:
    """A complete trace of an operation."""
    trace_id: str
    root_span: Span
    spans: List[Span] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_span(self, span: Span) -> None:
        self.spans.append(span)
    
    def get_total_duration(self) -> Optional[float]:
        return self.root_span.duration_ms


class Counter:
    """Thread-safe counter for metrics."""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._value = 0
        self._lock = threading.Lock()
    
    def inc(self, value: int = 1) -> None:
        with self._lock:
            self._value += value
    
    def get(self) -> int:
        with self._lock:
            return self._value
    
    def reset(self) -> None:
        with self._lock:
            self._value = 0


class Histogram:
    """Simple histogram for latency tracking."""
    
    def __init__(
        self, 
        name: str, 
        buckets: Optional[List[float]] = None,
        description: str = ""
    ):
        self.name = name
        self.description = description
        self.buckets = buckets or [10, 25, 50, 100, 250, 500, 1000, 2500, 5000]
        self._values: List[float] = []
        self._bucket_counts: Dict[float, int] = {b: 0 for b in self.buckets}
        self._lock = threading.Lock()
    
    def observe(self, value: float) -> None:
        with self._lock:
            self._values.append(value)
            for bucket in self.buckets:
                if value <= bucket:
                    self._bucket_counts[bucket] += 1
    
    def get_stats(self) -> Dict[str, float]:
        with self._lock:
            if not self._values:
                return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}
            
            import statistics
            return {
                "count": len(self._values),
                "sum": sum(self._values),
                "avg": statistics.mean(self._values),
                "min": min(self._values),
                "max": max(self._values),
                "median": statistics.median(self._values),
                "p95": self._percentile(95),
                "p99": self._percentile(99)
            }
    
    def _percentile(self, p: float) -> float:
        if not self._values:
            return 0
        sorted_values = sorted(self._values)
        index = int(len(sorted_values) * p / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def get_buckets(self) -> Dict[float, int]:
        with self._lock:
            return self._bucket_counts.copy()


class Gauge:
    """Thread-safe gauge for current values."""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._value = 0.0
        self._lock = threading.Lock()
    
    def set(self, value: float) -> None:
        with self._lock:
            self._value = value
    
    def inc(self, value: float = 1) -> None:
        with self._lock:
            self._value += value
    
    def dec(self, value: float = 1) -> None:
        with self._lock:
            self._value -= value
    
    def get(self) -> float:
        with self._lock:
            return self._value


class MetricsRegistry:
    """Registry for all metrics."""
    
    def __init__(self):
        self.counters: Dict[str, Counter] = {}
        self.histograms: Dict[str, Histogram] = {}
        self.gauges: Dict[str, Gauge] = {}
        self._lock = threading.Lock()
    
    def counter(self, name: str, description: str = "") -> Counter:
        with self._lock:
            if name not in self.counters:
                self.counters[name] = Counter(name, description)
            return self.counters[name]
    
    def histogram(
        self, 
        name: str, 
        buckets: Optional[List[float]] = None,
        description: str = ""
    ) -> Histogram:
        with self._lock:
            if name not in self.histograms:
                self.histograms[name] = Histogram(name, buckets, description)
            return self.histograms[name]
    
    def gauge(self, name: str, description: str = "") -> Gauge:
        with self._lock:
            if name not in self.gauges:
                self.gauges[name] = Gauge(name, description)
            return self.gauges[name]
    
    def get_all_metrics(self) -> Dict[str, Any]:
        return {
            "counters": {name: c.get() for name, c in self.counters.items()},
            "histograms": {name: h.get_stats() for name, h in self.histograms.items()},
            "gauges": {name: g.get() for name, g in self.gauges.items()}
        }


class EventLogger:
    """Logger for structured events."""
    
    def __init__(
        self,
        min_level: LogLevel = LogLevel.INFO,
        handlers: Optional[List[Callable[[TraceEvent], None]]] = None
    ):
        self.min_level = min_level
        self.handlers = handlers or []
        self.events: List[TraceEvent] = []
        self._lock = threading.Lock()
        self._event_counter = 0
    
    def add_handler(self, handler: Callable[[TraceEvent], None]) -> None:
        self.handlers.append(handler)
    
    def log(
        self,
        event_type: EventType,
        name: str,
        data: Dict[str, Any],
        trace_id: str = "",
        span_id: str = "",
        parent_span_id: Optional[str] = None,
        level: LogLevel = LogLevel.INFO,
        duration_ms: Optional[float] = None
    ) -> TraceEvent:
        if level.value < self.min_level.value:
            return None  # type: ignore
        
        with self._lock:
            self._event_counter += 1
            event_id = f"evt_{self._event_counter:08d}"
        
        event = TraceEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=datetime.now().isoformat(),
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name,
            data=data,
            duration_ms=duration_ms,
            level=level
        )
        
        with self._lock:
            self.events.append(event)
            # Keep only last 10000 events
            if len(self.events) > 10000:
                self.events = self.events[-10000:]
        
        # Call handlers
        for handler in self.handlers:
            try:
                handler(event)
            except Exception:
                pass  # Don't let handler errors affect logging
        
        return event
    
    def get_events(
        self,
        trace_id: Optional[str] = None,
        event_type: Optional[EventType] = None,
        limit: int = 100
    ) -> List[TraceEvent]:
        with self._lock:
            events = self.events.copy()
        
        if trace_id:
            events = [e for e in events if e.trace_id == trace_id]
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        return events[-limit:]


class Tracer:
    """
    Distributed tracing implementation.
    """
    
    def __init__(self, logger: Optional[EventLogger] = None):
        self.logger = logger or EventLogger()
        self.active_traces: Dict[str, Trace] = {}
        self._span_counter = 0
        self._trace_counter = 0
        self._lock = threading.Lock()
    
    def _generate_id(self, prefix: str) -> str:
        with self._lock:
            if prefix == "trace":
                self._trace_counter += 1
                return f"trace_{self._trace_counter:08d}"
            else:
                self._span_counter += 1
                return f"span_{self._span_counter:08d}"
    
    def start_trace(
        self,
        name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Trace:
        """Start a new trace."""
        trace_id = self._generate_id("trace")
        span_id = self._generate_id("span")
        
        root_span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=None,
            name=name,
            start_time=time.time()
        )
        
        trace = Trace(
            trace_id=trace_id,
            root_span=root_span,
            metadata=metadata or {}
        )
        
        self.active_traces[trace_id] = trace
        
        self.logger.log(
            EventType.START,
            name,
            {"metadata": metadata or {}},
            trace_id=trace_id,
            span_id=span_id
        )
        
        return trace
    
    def start_span(
        self,
        trace: Trace,
        name: str,
        parent_span_id: Optional[str] = None
    ) -> Span:
        """Start a new span within a trace."""
        span_id = self._generate_id("span")
        
        span = Span(
            trace_id=trace.trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id or trace.root_span.span_id,
            name=name,
            start_time=time.time()
        )
        
        trace.add_span(span)
        
        self.logger.log(
            EventType.START,
            name,
            {},
            trace_id=trace.trace_id,
            span_id=span_id,
            parent_span_id=span.parent_span_id
        )
        
        return span
    
    def end_span(self, span: Span) -> None:
        """End a span."""
        span.end()
        
        self.logger.log(
            EventType.END,
            span.name,
            {"status": span.status, "attributes": span.attributes},
            trace_id=span.trace_id,
            span_id=span.span_id,
            parent_span_id=span.parent_span_id,
            duration_ms=span.duration_ms
        )
    
    def end_trace(self, trace: Trace) -> None:
        """End a trace."""
        trace.root_span.end()
        
        self.logger.log(
            EventType.END,
            trace.root_span.name,
            {"total_spans": len(trace.spans)},
            trace_id=trace.trace_id,
            span_id=trace.root_span.span_id,
            duration_ms=trace.get_total_duration()
        )
        
        if trace.trace_id in self.active_traces:
            del self.active_traces[trace.trace_id]
    
    @contextmanager
    def trace(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        """Context manager for traces."""
        trace_obj = self.start_trace(name, metadata)
        try:
            yield trace_obj
        except Exception as e:
            trace_obj.root_span.status = "ERROR"
            self.logger.log(
                EventType.ERROR,
                name,
                {"error": str(e)},
                trace_id=trace_obj.trace_id,
                span_id=trace_obj.root_span.span_id,
                level=LogLevel.ERROR
            )
            raise
        finally:
            self.end_trace(trace_obj)
    
    @contextmanager
    def span(self, trace_obj: Trace, name: str):
        """Context manager for spans."""
        span_obj = self.start_span(trace_obj, name)
        try:
            yield span_obj
        except Exception as e:
            span_obj.status = "ERROR"
            self.logger.log(
                EventType.ERROR,
                name,
                {"error": str(e)},
                trace_id=span_obj.trace_id,
                span_id=span_obj.span_id,
                level=LogLevel.ERROR
            )
            raise
        finally:
            self.end_span(span_obj)


class TokenCounter:
    """Counter for token usage."""
    
    def __init__(self, metrics: MetricsRegistry):
        self.metrics = metrics
        self.input_tokens = metrics.counter("tokens_input", "Input tokens used")
        self.output_tokens = metrics.counter("tokens_output", "Output tokens used")
        self.total_tokens = metrics.counter("tokens_total", "Total tokens used")
    
    def count(
        self,
        input_tokens: int,
        output_tokens: int,
        trace_id: Optional[str] = None
    ) -> Dict[str, int]:
        self.input_tokens.inc(input_tokens)
        self.output_tokens.inc(output_tokens)
        self.total_tokens.inc(input_tokens + output_tokens)
        
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens
        }
    
    def get_usage(self) -> Dict[str, int]:
        return {
            "input_tokens": self.input_tokens.get(),
            "output_tokens": self.output_tokens.get(),
            "total_tokens": self.total_tokens.get()
        }


class ObservabilitySystem:
    """
    Complete observability system.
    """
    
    def __init__(self, min_log_level: LogLevel = LogLevel.INFO):
        self.metrics = MetricsRegistry()
        self.logger = EventLogger(min_level=min_log_level)
        self.tracer = Tracer(self.logger)
        self.token_counter = TokenCounter(self.metrics)
        
        # Pre-create common metrics
        self._setup_common_metrics()
    
    def _setup_common_metrics(self) -> None:
        """Set up commonly used metrics."""
        # Counters
        self.requests = self.metrics.counter("requests_total", "Total requests")
        self.errors = self.metrics.counter("errors_total", "Total errors")
        self.reasoning_steps = self.metrics.counter("reasoning_steps", "Reasoning steps taken")
        self.tool_calls = self.metrics.counter("tool_calls", "Tool calls made")
        
        # Histograms
        self.request_latency = self.metrics.histogram(
            "request_latency_ms",
            description="Request latency in milliseconds"
        )
        self.reasoning_latency = self.metrics.histogram(
            "reasoning_latency_ms",
            description="Reasoning step latency in milliseconds"
        )
        self.tool_latency = self.metrics.histogram(
            "tool_latency_ms",
            description="Tool call latency in milliseconds"
        )
        
        # Gauges
        self.active_requests = self.metrics.gauge("active_requests", "Currently active requests")
        self.memory_entries = self.metrics.gauge("memory_entries", "Number of memory entries")
    
    def log_request(
        self,
        query: str,
        trace_id: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log an incoming request."""
        self.requests.inc()
        self.active_requests.inc()
        
        self.logger.log(
            EventType.START,
            "request",
            {"query": query[:200], "metadata": metadata or {}},
            trace_id=trace_id
        )
    
    def log_response(
        self,
        response: str,
        latency_ms: float,
        trace_id: str = "",
        success: bool = True
    ) -> None:
        """Log a response."""
        self.active_requests.dec()
        self.request_latency.observe(latency_ms)
        
        if not success:
            self.errors.inc()
        
        self.logger.log(
            EventType.END,
            "response",
            {"response_length": len(response), "success": success},
            trace_id=trace_id,
            duration_ms=latency_ms,
            level=LogLevel.INFO if success else LogLevel.ERROR
        )
    
    def log_reasoning_step(
        self,
        step_name: str,
        step_data: Dict[str, Any],
        latency_ms: float,
        trace_id: str = ""
    ) -> None:
        """Log a reasoning step."""
        self.reasoning_steps.inc()
        self.reasoning_latency.observe(latency_ms)
        
        self.logger.log(
            EventType.REASONING_STEP,
            step_name,
            step_data,
            trace_id=trace_id,
            duration_ms=latency_ms
        )
    
    def log_tool_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        result: Any,
        latency_ms: float,
        success: bool = True,
        trace_id: str = ""
    ) -> None:
        """Log a tool call."""
        self.tool_calls.inc()
        self.tool_latency.observe(latency_ms)
        
        if not success:
            self.errors.inc()
        
        self.logger.log(
            EventType.TOOL_RESULT if success else EventType.TOOL_ERROR,
            f"tool:{tool_name}",
            {"args": args, "result": str(result)[:500], "success": success},
            trace_id=trace_id,
            duration_ms=latency_ms,
            level=LogLevel.INFO if success else LogLevel.ERROR
        )
    
    def log_tokens(
        self,
        input_tokens: int,
        output_tokens: int,
        trace_id: str = ""
    ) -> None:
        """Log token usage."""
        usage = self.token_counter.count(input_tokens, output_tokens, trace_id)
        
        self.logger.log(
            EventType.TOKEN_COUNT,
            "tokens",
            usage,
            trace_id=trace_id
        )
    
    def get_summary(self) -> Dict[str, Any]:
        """Get observability summary."""
        return {
            "metrics": self.metrics.get_all_metrics(),
            "token_usage": self.token_counter.get_usage(),
            "recent_events": len(self.logger.events),
            "active_traces": len(self.tracer.active_traces)
        }
    
    def export_events(
        self,
        trace_id: Optional[str] = None,
        format_type: str = "json"
    ) -> str:
        """Export events for external consumption."""
        events = self.logger.get_events(trace_id=trace_id)
        
        if format_type == "json":
            return json.dumps([e.to_dict() for e in events], indent=2)
        elif format_type == "jsonl":
            return "\n".join(e.to_json() for e in events)
        else:
            # Simple text format
            lines = []
            for e in events:
                lines.append(
                    f"[{e.timestamp}] {e.level.name} {e.event_type.value}: {e.name}"
                )
            return "\n".join(lines)
