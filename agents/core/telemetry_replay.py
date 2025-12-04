"""
Telemetry and Replay System - Advanced Enhancement

Provides session logging and replay capabilities:
- Comprehensive event logging
- Session recording and replay
- Performance metrics collection
- Debugging and analysis tools
"""

from typing import List, Dict, Any, Optional, Tuple, Callable, Iterator, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from abc import ABC, abstractmethod
import json
import hashlib
import copy


class EventType(Enum):
    """Types of telemetry events."""
    INPUT = "input"  # User input
    OUTPUT = "output"  # Agent output
    TOOL_CALL = "tool_call"  # Tool invocation
    TOOL_RESULT = "tool_result"  # Tool result
    RETRIEVAL = "retrieval"  # Retrieval operation
    REASONING = "reasoning"  # Reasoning step
    DECISION = "decision"  # Decision made
    ERROR = "error"  # Error occurred
    METRIC = "metric"  # Performance metric
    STATE = "state"  # State change
    CHECKPOINT = "checkpoint"  # Explicit checkpoint


class LogLevel(Enum):
    """Logging levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class TelemetryEvent:
    """A single telemetry event."""
    event_id: str
    event_type: EventType
    timestamp: datetime
    session_id: str
    data: Dict[str, Any]
    level: LogLevel = LogLevel.INFO
    parent_event_id: Optional[str] = None
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "data": self.data,
            "level": self.level.value,
            "parent_event_id": self.parent_event_id,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TelemetryEvent":
        """Create from dictionary."""
        return cls(
            event_id=data["event_id"],
            event_type=EventType(data["event_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            session_id=data["session_id"],
            data=data["data"],
            level=LogLevel(data.get("level", "info")),
            parent_event_id=data.get("parent_event_id"),
            duration_ms=data.get("duration_ms"),
            metadata=data.get("metadata", {})
        )


@dataclass
class Session:
    """A recorded session."""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    events: List[TelemetryEvent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    checkpoints: Dict[str, int] = field(default_factory=dict)  # name -> event index
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Get session duration."""
        if self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def event_count(self) -> int:
        """Get event count."""
        return len(self.events)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "events": [e.to_dict() for e in self.events],
            "metadata": self.metadata,
            "checkpoints": self.checkpoints
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Create from dictionary."""
        return cls(
            session_id=data["session_id"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None,
            events=[TelemetryEvent.from_dict(e) for e in data.get("events", [])],
            metadata=data.get("metadata", {}),
            checkpoints=data.get("checkpoints", {})
        )


@dataclass
class PerformanceMetrics:
    """Aggregated performance metrics."""
    total_events: int
    total_duration_ms: float
    avg_response_time_ms: float
    error_count: int
    tool_calls: int
    retrievals: int
    by_event_type: Dict[str, int]
    latency_percentiles: Dict[str, float]


class EventStore(ABC):
    """Abstract base for event storage."""
    
    @abstractmethod
    def store(self, event: TelemetryEvent):
        """Store an event."""
    
    @abstractmethod
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
    
    @abstractmethod
    def query(
        self,
        session_id: Optional[str] = None,
        event_type: Optional[EventType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[TelemetryEvent]:
        """Query events."""


class InMemoryEventStore(EventStore):
    """In-memory event storage."""
    
    def __init__(self, max_events: int = 10000):
        self.max_events = max_events
        self.events: List[TelemetryEvent] = []
        self.sessions: Dict[str, Session] = {}
    
    def store(self, event: TelemetryEvent):
        """Store an event."""
        # Ensure session exists
        if event.session_id not in self.sessions:
            self.sessions[event.session_id] = Session(
                session_id=event.session_id,
                start_time=event.timestamp
            )
        
        session = self.sessions[event.session_id]
        session.events.append(event)
        session.end_time = event.timestamp
        
        # Add to global list
        self.events.append(event)
        
        # Trim if needed
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self.sessions.get(session_id)
    
    def query(
        self,
        session_id: Optional[str] = None,
        event_type: Optional[EventType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[TelemetryEvent]:
        """Query events."""
        results = self.events
        
        if session_id:
            results = [e for e in results if e.session_id == session_id]
        
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        
        if start_time:
            results = [e for e in results if e.timestamp >= start_time]
        
        if end_time:
            results = [e for e in results if e.timestamp <= end_time]
        
        return results


class TelemetryLogger:
    """Main telemetry logging system."""
    
    def __init__(
        self,
        store: Optional[EventStore] = None,
        default_level: LogLevel = LogLevel.INFO
    ):
        self.store = store or InMemoryEventStore()
        self.default_level = default_level
        self._event_counter = 0
        self._active_spans: Dict[str, datetime] = {}
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        self._event_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"evt_{timestamp}_{self._event_counter}"
    
    def log(
        self,
        session_id: str,
        event_type: EventType,
        data: Dict[str, Any],
        level: Optional[LogLevel] = None,
        parent_event_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TelemetryEvent:
        """Log a telemetry event."""
        event = TelemetryEvent(
            event_id=self._generate_event_id(),
            event_type=event_type,
            timestamp=datetime.now(),
            session_id=session_id,
            data=data,
            level=level or self.default_level,
            parent_event_id=parent_event_id,
            metadata=metadata or {}
        )
        
        self.store.store(event)
        return event
    
    def log_input(
        self,
        session_id: str,
        input_text: str,
        **kwargs: Any
    ) -> TelemetryEvent:
        """Log user input."""
        return self.log(
            session_id=session_id,
            event_type=EventType.INPUT,
            data={"text": input_text, **kwargs}
        )
    
    def log_output(
        self,
        session_id: str,
        output_text: str,
        **kwargs: Any
    ) -> TelemetryEvent:
        """Log agent output."""
        return self.log(
            session_id=session_id,
            event_type=EventType.OUTPUT,
            data={"text": output_text, **kwargs}
        )
    
    def log_tool_call(
        self,
        session_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        **kwargs: Any
    ) -> TelemetryEvent:
        """Log tool invocation."""
        return self.log(
            session_id=session_id,
            event_type=EventType.TOOL_CALL,
            data={"tool": tool_name, "arguments": arguments, **kwargs}
        )
    
    def log_tool_result(
        self,
        session_id: str,
        tool_name: str,
        result: Any,
        success: bool = True,
        **kwargs: Any
    ) -> TelemetryEvent:
        """Log tool result."""
        return self.log(
            session_id=session_id,
            event_type=EventType.TOOL_RESULT,
            data={"tool": tool_name, "result": result, "success": success, **kwargs}
        )
    
    def log_error(
        self,
        session_id: str,
        error_type: str,
        error_message: str,
        **kwargs: Any
    ) -> TelemetryEvent:
        """Log an error."""
        return self.log(
            session_id=session_id,
            event_type=EventType.ERROR,
            data={"type": error_type, "message": error_message, **kwargs},
            level=LogLevel.ERROR
        )
    
    def log_metric(
        self,
        session_id: str,
        metric_name: str,
        value: Union[int, float],
        unit: str = "",
        **kwargs: Any
    ) -> TelemetryEvent:
        """Log a metric."""
        return self.log(
            session_id=session_id,
            event_type=EventType.METRIC,
            data={"name": metric_name, "value": value, "unit": unit, **kwargs}
        )
    
    def start_span(
        self,
        session_id: str,
        span_name: str
    ) -> str:
        """Start a timed span."""
        span_id = f"span_{span_name}_{datetime.now().timestamp()}"
        self._active_spans[span_id] = datetime.now()
        return span_id
    
    def end_span(
        self,
        session_id: str,
        span_id: str,
        span_name: str,
        **kwargs: Any
    ) -> TelemetryEvent:
        """End a timed span."""
        start_time = self._active_spans.pop(span_id, datetime.now())
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        event = self.log(
            session_id=session_id,
            event_type=EventType.METRIC,
            data={"name": f"span_{span_name}", "duration_ms": duration_ms, **kwargs}
        )
        event.duration_ms = duration_ms
        return event
    
    def checkpoint(
        self,
        session_id: str,
        checkpoint_name: str,
        state: Optional[Dict[str, Any]] = None
    ) -> TelemetryEvent:
        """Create a checkpoint."""
        session = self.store.get_session(session_id)
        if session:
            session.checkpoints[checkpoint_name] = len(session.events)
        
        return self.log(
            session_id=session_id,
            event_type=EventType.CHECKPOINT,
            data={"name": checkpoint_name, "state": state or {}}
        )


class SessionReplay:
    """Replays recorded sessions."""
    
    def __init__(self, store: EventStore):
        self.store = store
        self._replay_position = 0
        self._current_session: Optional[Session] = None
    
    def load_session(self, session_id: str) -> bool:
        """Load a session for replay."""
        self._current_session = self.store.get_session(session_id)
        self._replay_position = 0
        return self._current_session is not None
    
    def get_events(
        self,
        start: int = 0,
        count: Optional[int] = None
    ) -> List[TelemetryEvent]:
        """Get events from current session."""
        if not self._current_session:
            return []
        
        events = self._current_session.events[start:]
        if count is not None:
            events = events[:count]
        
        return events
    
    def step_forward(self) -> Optional[TelemetryEvent]:
        """Step forward one event."""
        if not self._current_session:
            return None
        
        if self._replay_position >= len(self._current_session.events):
            return None
        
        event = self._current_session.events[self._replay_position]
        self._replay_position += 1
        return event
    
    def step_backward(self) -> Optional[TelemetryEvent]:
        """Step backward one event."""
        if not self._current_session:
            return None
        
        if self._replay_position <= 0:
            return None
        
        self._replay_position -= 1
        return self._current_session.events[self._replay_position]
    
    def seek_to_checkpoint(self, checkpoint_name: str) -> bool:
        """Seek to a named checkpoint."""
        if not self._current_session:
            return False
        
        if checkpoint_name in self._current_session.checkpoints:
            self._replay_position = self._current_session.checkpoints[checkpoint_name]
            return True
        
        return False
    
    def seek_to_position(self, position: int) -> bool:
        """Seek to a specific position."""
        if not self._current_session:
            return False
        
        if 0 <= position <= len(self._current_session.events):
            self._replay_position = position
            return True
        
        return False
    
    def iterate_events(
        self,
        event_types: Optional[List[EventType]] = None
    ) -> Iterator[TelemetryEvent]:
        """Iterate through events."""
        if not self._current_session:
            return
        
        for event in self._current_session.events:
            if event_types is None or event.event_type in event_types:
                yield event
    
    def get_input_output_pairs(self) -> List[Tuple[str, str]]:
        """Get input/output pairs from session."""
        if not self._current_session:
            return []
        
        pairs = []
        current_input = None
        
        for event in self._current_session.events:
            if event.event_type == EventType.INPUT:
                current_input = event.data.get("text", "")
            elif event.event_type == EventType.OUTPUT and current_input:
                output = event.data.get("text", "")
                pairs.append((current_input, output))
                current_input = None
        
        return pairs


class MetricsAggregator:
    """Aggregates metrics from sessions."""
    
    def __init__(self, store: EventStore):
        self.store = store
    
    def aggregate_session(self, session_id: str) -> PerformanceMetrics:
        """Aggregate metrics for a session."""
        session = self.store.get_session(session_id)
        if not session:
            return self._empty_metrics()
        
        return self._aggregate_events(session.events)
    
    def aggregate_range(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> PerformanceMetrics:
        """Aggregate metrics for a time range."""
        events = self.store.query(start_time=start_time, end_time=end_time)
        return self._aggregate_events(events)
    
    def _aggregate_events(
        self,
        events: List[TelemetryEvent]
    ) -> PerformanceMetrics:
        """Aggregate metrics from events."""
        if not events:
            return self._empty_metrics()
        
        total_duration = 0.0
        latencies: List[float] = []
        error_count = 0
        tool_calls = 0
        retrievals = 0
        by_type: Dict[str, int] = {}
        
        for event in events:
            # Count by type
            type_name = event.event_type.value
            by_type[type_name] = by_type.get(type_name, 0) + 1
            
            # Track duration
            if event.duration_ms:
                total_duration += event.duration_ms
                latencies.append(event.duration_ms)
            
            # Count specific types
            if event.event_type == EventType.ERROR:
                error_count += 1
            elif event.event_type == EventType.TOOL_CALL:
                tool_calls += 1
            elif event.event_type == EventType.RETRIEVAL:
                retrievals += 1
        
        # Compute percentiles
        percentiles = self._compute_percentiles(latencies)
        
        return PerformanceMetrics(
            total_events=len(events),
            total_duration_ms=total_duration,
            avg_response_time_ms=total_duration / max(len(latencies), 1),
            error_count=error_count,
            tool_calls=tool_calls,
            retrievals=retrievals,
            by_event_type=by_type,
            latency_percentiles=percentiles
        )
    
    def _compute_percentiles(
        self,
        values: List[float]
    ) -> Dict[str, float]:
        """Compute latency percentiles."""
        if not values:
            return {"p50": 0.0, "p90": 0.0, "p99": 0.0}
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        return {
            "p50": sorted_values[int(n * 0.5)],
            "p90": sorted_values[int(n * 0.9)] if n > 1 else sorted_values[-1],
            "p99": sorted_values[int(n * 0.99)] if n > 1 else sorted_values[-1]
        }
    
    def _empty_metrics(self) -> PerformanceMetrics:
        """Return empty metrics."""
        return PerformanceMetrics(
            total_events=0,
            total_duration_ms=0.0,
            avg_response_time_ms=0.0,
            error_count=0,
            tool_calls=0,
            retrievals=0,
            by_event_type={},
            latency_percentiles={"p50": 0.0, "p90": 0.0, "p99": 0.0}
        )


class SessionExporter:
    """Exports sessions to various formats."""
    
    def __init__(self, store: EventStore):
        self.store = store
    
    def to_json(self, session_id: str) -> str:
        """Export session to JSON."""
        session = self.store.get_session(session_id)
        if not session:
            return "{}"
        
        return json.dumps(session.to_dict(), indent=2)
    
    def to_conversation(self, session_id: str) -> List[Dict[str, str]]:
        """Export session as conversation format."""
        session = self.store.get_session(session_id)
        if not session:
            return []
        
        conversation = []
        for event in session.events:
            if event.event_type == EventType.INPUT:
                conversation.append({
                    "role": "user",
                    "content": event.data.get("text", "")
                })
            elif event.event_type == EventType.OUTPUT:
                conversation.append({
                    "role": "assistant",
                    "content": event.data.get("text", "")
                })
        
        return conversation
    
    def to_trace(self, session_id: str) -> List[Dict[str, Any]]:
        """Export session as trace format."""
        session = self.store.get_session(session_id)
        if not session:
            return []
        
        trace = []
        for event in session.events:
            trace.append({
                "timestamp": event.timestamp.isoformat(),
                "type": event.event_type.value,
                "data": event.data,
                "duration_ms": event.duration_ms
            })
        
        return trace


class DebugHelper:
    """Debugging utilities for sessions."""
    
    def __init__(self, store: EventStore):
        self.store = store
    
    def find_errors(self, session_id: str) -> List[TelemetryEvent]:
        """Find all errors in a session."""
        return self.store.query(
            session_id=session_id,
            event_type=EventType.ERROR
        )
    
    def get_slow_operations(
        self,
        session_id: str,
        threshold_ms: float = 1000.0
    ) -> List[TelemetryEvent]:
        """Find slow operations."""
        session = self.store.get_session(session_id)
        if not session:
            return []
        
        return [
            e for e in session.events
            if e.duration_ms and e.duration_ms > threshold_ms
        ]
    
    def get_tool_usage(self, session_id: str) -> Dict[str, int]:
        """Get tool usage counts."""
        events = self.store.query(
            session_id=session_id,
            event_type=EventType.TOOL_CALL
        )
        
        usage: Dict[str, int] = {}
        for event in events:
            tool = event.data.get("tool", "unknown")
            usage[tool] = usage.get(tool, 0) + 1
        
        return usage
    
    def diff_sessions(
        self,
        session_id_1: str,
        session_id_2: str
    ) -> Dict[str, Any]:
        """Compare two sessions."""
        session1 = self.store.get_session(session_id_1)
        session2 = self.store.get_session(session_id_2)
        
        if not session1 or not session2:
            return {"error": "One or both sessions not found"}
        
        return {
            "event_count_diff": len(session1.events) - len(session2.events),
            "duration_diff": (
                (session1.duration.total_seconds() if session1.duration else 0) -
                (session2.duration.total_seconds() if session2.duration else 0)
            ),
            "event_type_diff": self._diff_event_types(session1, session2)
        }
    
    def _diff_event_types(
        self,
        session1: Session,
        session2: Session
    ) -> Dict[str, int]:
        """Diff event type counts."""
        types1: Dict[str, int] = {}
        types2: Dict[str, int] = {}
        
        for e in session1.events:
            types1[e.event_type.value] = types1.get(e.event_type.value, 0) + 1
        
        for e in session2.events:
            types2[e.event_type.value] = types2.get(e.event_type.value, 0) + 1
        
        all_types = set(types1.keys()) | set(types2.keys())
        return {
            t: types1.get(t, 0) - types2.get(t, 0)
            for t in all_types
        }


# Factory functions
def create_telemetry_logger(
    max_events: int = 10000
) -> TelemetryLogger:
    """Create a telemetry logger."""
    store = InMemoryEventStore(max_events=max_events)
    return TelemetryLogger(store=store)


def create_session_replay(logger: TelemetryLogger) -> SessionReplay:
    """Create a session replay from a logger."""
    return SessionReplay(store=logger.store)


def create_metrics_aggregator(logger: TelemetryLogger) -> MetricsAggregator:
    """Create a metrics aggregator from a logger."""
    return MetricsAggregator(store=logger.store)
