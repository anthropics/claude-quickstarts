"""
Trace logger for reasoning/decision/planning events.

Stores structured events in-memory; can be extended to persist JSONL.
"""
from typing import List, Dict, Any
from datetime import datetime


class TraceLogger:
    def __init__(self, keep_last: int = 200):
        self.keep_last = keep_last
        self._events: List[Dict[str, Any]] = []

    def log(self, event_type: str, payload: Dict[str, Any]) -> None:
        event = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "payload": payload,
        }
        self._events.append(event)
        if len(self._events) > self.keep_last:
            self._events = self._events[-self.keep_last:]

    def get_events(self) -> List[Dict[str, Any]]:
        return list(self._events)
