"""
UI Hooks System - Phase 2 Enhancement

Provides event callbacks for UI integration:
- Progress tracking
- Status updates
- Real-time streaming
- User interaction callbacks
"""

from typing import Dict, Any, Optional, Callable, List, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading
from collections import deque
import json


class EventType(Enum):
    """Types of UI events."""
    # Progress events
    PROGRESS_START = "progress_start"
    PROGRESS_UPDATE = "progress_update"
    PROGRESS_COMPLETE = "progress_complete"
    PROGRESS_ERROR = "progress_error"
    
    # Status events
    STATUS_CHANGE = "status_change"
    STATUS_MESSAGE = "status_message"
    
    # Agent events
    AGENT_THINKING = "agent_thinking"
    AGENT_ACTING = "agent_acting"
    AGENT_WAITING = "agent_waiting"
    AGENT_COMPLETE = "agent_complete"
    
    # Reasoning events
    REASONING_STEP = "reasoning_step"
    DECISION_MADE = "decision_made"
    EVIDENCE_FOUND = "evidence_found"
    
    # User interaction
    CLARIFICATION_NEEDED = "clarification_needed"
    USER_INPUT_REQUIRED = "user_input_required"
    CONFIRMATION_NEEDED = "confirmation_needed"
    
    # Stream events
    TOKEN_GENERATED = "token_generated"
    CHUNK_READY = "chunk_ready"


class AgentStatus(Enum):
    """Agent status states."""
    IDLE = "idle"
    INITIALIZING = "initializing"
    THINKING = "thinking"
    ACTING = "acting"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class UIEvent:
    """An event for UI consumption."""
    event_type: EventType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "agent"
    event_id: str = ""
    
    def __post_init__(self):
        if not self.event_id:
            self.event_id = f"{self.event_type.value}_{int(self.timestamp.timestamp() * 1000)}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


@dataclass
class ProgressInfo:
    """Progress information for a task."""
    task_id: str
    title: str
    current: int = 0
    total: int = 100
    message: str = ""
    status: str = "running"  # running, complete, error
    sub_tasks: List["ProgressInfo"] = field(default_factory=list)
    
    @property
    def percentage(self) -> float:
        """Get completion percentage."""
        if self.total == 0:
            return 0
        return (self.current / self.total) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "title": self.title,
            "current": self.current,
            "total": self.total,
            "percentage": self.percentage,
            "message": self.message,
            "status": self.status,
            "sub_tasks": [t.to_dict() for t in self.sub_tasks]
        }


class EventBus:
    """Central event bus for UI events."""
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable[[UIEvent], None]]] = {}
        self._global_subscribers: List[Callable[[UIEvent], None]] = []
        self._event_history: deque = deque(maxlen=1000)
        self._lock = threading.Lock()
    
    def subscribe(
        self,
        event_type: EventType,
        callback: Callable[[UIEvent], None]
    ) -> str:
        """Subscribe to a specific event type."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
            return f"sub_{event_type.value}_{len(self._subscribers[event_type])}"
    
    def subscribe_all(
        self,
        callback: Callable[[UIEvent], None]
    ) -> str:
        """Subscribe to all events."""
        with self._lock:
            self._global_subscribers.append(callback)
            return f"sub_global_{len(self._global_subscribers)}"
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events (simplified - would need proper tracking)."""
        # In production, would maintain a mapping of subscription_id to callback
        return True
    
    def emit(self, event: UIEvent) -> None:
        """Emit an event to all subscribers."""
        with self._lock:
            self._event_history.append(event)
            
            # Notify specific subscribers
            subscribers = self._subscribers.get(event.event_type, [])
            for callback in subscribers:
                try:
                    callback(event)
                except Exception:
                    pass
            
            # Notify global subscribers
            for callback in self._global_subscribers:
                try:
                    callback(event)
                except Exception:
                    pass
    
    def get_history(self, limit: int = 100) -> List[UIEvent]:
        """Get recent event history."""
        with self._lock:
            return list(self._event_history)[-limit:]
    
    def clear_history(self) -> None:
        """Clear event history."""
        with self._lock:
            self._event_history.clear()


class ProgressTracker:
    """Tracks and reports progress for tasks."""
    
    def __init__(self, event_bus: EventBus):
        self._bus = event_bus
        self._tasks: Dict[str, ProgressInfo] = {}
        self._lock = threading.Lock()
    
    def start_task(
        self,
        task_id: str,
        title: str,
        total: int = 100
    ) -> ProgressInfo:
        """Start tracking a new task."""
        with self._lock:
            progress = ProgressInfo(
                task_id=task_id,
                title=title,
                total=total,
                status="running"
            )
            self._tasks[task_id] = progress
            
            self._bus.emit(UIEvent(
                event_type=EventType.PROGRESS_START,
                data=progress.to_dict()
            ))
            
            return progress
    
    def update_progress(
        self,
        task_id: str,
        current: Optional[int] = None,
        message: Optional[str] = None,
        increment: int = 0
    ) -> Optional[ProgressInfo]:
        """Update progress for a task."""
        with self._lock:
            progress = self._tasks.get(task_id)
            if not progress:
                return None
            
            if current is not None:
                progress.current = current
            elif increment > 0:
                progress.current += increment
            
            if message:
                progress.message = message
            
            self._bus.emit(UIEvent(
                event_type=EventType.PROGRESS_UPDATE,
                data=progress.to_dict()
            ))
            
            return progress
    
    def complete_task(
        self,
        task_id: str,
        message: str = "Complete"
    ) -> Optional[ProgressInfo]:
        """Mark a task as complete."""
        with self._lock:
            progress = self._tasks.get(task_id)
            if not progress:
                return None
            
            progress.current = progress.total
            progress.status = "complete"
            progress.message = message
            
            self._bus.emit(UIEvent(
                event_type=EventType.PROGRESS_COMPLETE,
                data=progress.to_dict()
            ))
            
            return progress
    
    def fail_task(
        self,
        task_id: str,
        error: str
    ) -> Optional[ProgressInfo]:
        """Mark a task as failed."""
        with self._lock:
            progress = self._tasks.get(task_id)
            if not progress:
                return None
            
            progress.status = "error"
            progress.message = error
            
            self._bus.emit(UIEvent(
                event_type=EventType.PROGRESS_ERROR,
                data={**progress.to_dict(), "error": error}
            ))
            
            return progress
    
    def get_task(self, task_id: str) -> Optional[ProgressInfo]:
        """Get current progress for a task."""
        with self._lock:
            return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> Dict[str, ProgressInfo]:
        """Get all active tasks."""
        with self._lock:
            return dict(self._tasks)


class StatusManager:
    """Manages agent status updates."""
    
    def __init__(self, event_bus: EventBus):
        self._bus = event_bus
        self._status = AgentStatus.IDLE
        self._message = ""
        self._details: Dict[str, Any] = {}
        self._lock = threading.Lock()
    
    def set_status(
        self,
        status: AgentStatus,
        message: str = "",
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Set the current agent status."""
        with self._lock:
            self._status = status
            self._message = message
            self._details = details or {}
            
            self._bus.emit(UIEvent(
                event_type=EventType.STATUS_CHANGE,
                data={
                    "status": status.value,
                    "message": message,
                    "details": self._details
                }
            ))
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        with self._lock:
            return {
                "status": self._status.value,
                "message": self._message,
                "details": self._details
            }
    
    def send_message(self, message: str, level: str = "info") -> None:
        """Send a status message."""
        self._bus.emit(UIEvent(
            event_type=EventType.STATUS_MESSAGE,
            data={"message": message, "level": level}
        ))


class ReasoningReporter:
    """Reports reasoning steps for transparency."""
    
    def __init__(self, event_bus: EventBus):
        self._bus = event_bus
        self._steps: List[Dict[str, Any]] = []
    
    def report_step(
        self,
        step_type: str,
        description: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Report a reasoning step."""
        step = {
            "step_number": len(self._steps) + 1,
            "type": step_type,
            "description": description,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
        self._steps.append(step)
        
        self._bus.emit(UIEvent(
            event_type=EventType.REASONING_STEP,
            data=step
        ))
    
    def report_decision(
        self,
        decision: str,
        reasoning: str,
        alternatives: Optional[List[str]] = None,
        confidence: float = 0.0
    ) -> None:
        """Report a decision made."""
        self._bus.emit(UIEvent(
            event_type=EventType.DECISION_MADE,
            data={
                "decision": decision,
                "reasoning": reasoning,
                "alternatives": alternatives or [],
                "confidence": confidence
            }
        ))
    
    def report_evidence(
        self,
        claim: str,
        evidence: str,
        source: str,
        confidence: float
    ) -> None:
        """Report evidence found."""
        self._bus.emit(UIEvent(
            event_type=EventType.EVIDENCE_FOUND,
            data={
                "claim": claim,
                "evidence": evidence,
                "source": source,
                "confidence": confidence
            }
        ))
    
    def get_steps(self) -> List[Dict[str, Any]]:
        """Get all reasoning steps."""
        return list(self._steps)
    
    def clear(self) -> None:
        """Clear reasoning history."""
        self._steps.clear()


class StreamHandler:
    """Handles streaming output for UI."""
    
    def __init__(self, event_bus: EventBus):
        self._bus = event_bus
        self._buffer = ""
        self._chunk_size = 50
    
    def stream_token(self, token: str) -> None:
        """Stream a single token."""
        self._buffer += token
        
        self._bus.emit(UIEvent(
            event_type=EventType.TOKEN_GENERATED,
            data={"token": token, "buffer": self._buffer}
        ))
        
        # Emit chunk when buffer is large enough
        if len(self._buffer) >= self._chunk_size:
            self.flush()
    
    def flush(self) -> None:
        """Flush the current buffer as a chunk."""
        if self._buffer:
            self._bus.emit(UIEvent(
                event_type=EventType.CHUNK_READY,
                data={"chunk": self._buffer}
            ))
            self._buffer = ""
    
    def get_buffer(self) -> str:
        """Get current buffer contents."""
        return self._buffer


class UserInteractionHandler:
    """Handles user interaction requests."""
    
    def __init__(self, event_bus: EventBus):
        self._bus = event_bus
        self._pending_requests: Dict[str, Dict[str, Any]] = {}
        self._responses: Dict[str, Any] = {}
        self._lock = threading.Lock()
    
    def request_clarification(
        self,
        request_id: str,
        question: str,
        options: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Request clarification from user."""
        with self._lock:
            request = {
                "request_id": request_id,
                "question": question,
                "options": options,
                "context": context or {},
                "timestamp": datetime.now().isoformat()
            }
            self._pending_requests[request_id] = request
            
            self._bus.emit(UIEvent(
                event_type=EventType.CLARIFICATION_NEEDED,
                data=request
            ))
    
    def request_input(
        self,
        request_id: str,
        prompt: str,
        input_type: str = "text",
        validation: Optional[Dict[str, Any]] = None
    ) -> None:
        """Request input from user."""
        with self._lock:
            request = {
                "request_id": request_id,
                "prompt": prompt,
                "input_type": input_type,
                "validation": validation or {},
                "timestamp": datetime.now().isoformat()
            }
            self._pending_requests[request_id] = request
            
            self._bus.emit(UIEvent(
                event_type=EventType.USER_INPUT_REQUIRED,
                data=request
            ))
    
    def request_confirmation(
        self,
        request_id: str,
        message: str,
        action: str,
        severity: str = "info"
    ) -> None:
        """Request confirmation from user."""
        with self._lock:
            request = {
                "request_id": request_id,
                "message": message,
                "action": action,
                "severity": severity,
                "timestamp": datetime.now().isoformat()
            }
            self._pending_requests[request_id] = request
            
            self._bus.emit(UIEvent(
                event_type=EventType.CONFIRMATION_NEEDED,
                data=request
            ))
    
    def provide_response(self, request_id: str, response: Any) -> bool:
        """Provide response to a pending request."""
        with self._lock:
            if request_id not in self._pending_requests:
                return False
            
            self._responses[request_id] = response
            del self._pending_requests[request_id]
            return True
    
    def get_response(self, request_id: str) -> Optional[Any]:
        """Get response for a request."""
        with self._lock:
            return self._responses.get(request_id)
    
    def has_pending(self, request_id: str) -> bool:
        """Check if a request is pending."""
        with self._lock:
            return request_id in self._pending_requests


class UIHooks:
    """
    Main UI hooks interface.
    
    Provides unified access to all UI integration features.
    """
    
    def __init__(self):
        self.event_bus = EventBus()
        self.progress = ProgressTracker(self.event_bus)
        self.status = StatusManager(self.event_bus)
        self.reasoning = ReasoningReporter(self.event_bus)
        self.stream = StreamHandler(self.event_bus)
        self.interaction = UserInteractionHandler(self.event_bus)
    
    def subscribe(
        self,
        event_type: EventType,
        callback: Callable[[UIEvent], None]
    ) -> str:
        """Subscribe to an event type."""
        return self.event_bus.subscribe(event_type, callback)
    
    def subscribe_all(self, callback: Callable[[UIEvent], None]) -> str:
        """Subscribe to all events."""
        return self.event_bus.subscribe_all(callback)
    
    def emit_custom(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        source: str = "agent"
    ) -> None:
        """Emit a custom event."""
        self.event_bus.emit(UIEvent(
            event_type=event_type,
            data=data,
            source=source
        ))
    
    def get_event_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get event history as dictionaries."""
        return [e.to_dict() for e in self.event_bus.get_history(limit)]


# Convenience functions

def create_ui_hooks() -> UIHooks:
    """Create a UI hooks instance."""
    return UIHooks()


def create_console_logger(hooks: UIHooks) -> None:
    """Attach console logging to UI hooks."""
    def log_event(event: UIEvent):
        print(f"[{event.event_type.value}] {event.data}")
    
    hooks.subscribe_all(log_event)


def create_json_logger(hooks: UIHooks, output_file: str) -> None:
    """Attach JSON file logging to UI hooks."""
    import threading
    lock = threading.Lock()
    
    def log_event(event: UIEvent):
        with lock:
            with open(output_file, "a") as f:
                f.write(event.to_json() + "\n")
    
    hooks.subscribe_all(log_event)
