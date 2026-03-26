"""Typed state models for the autonomous coding V3.1 orchestrator."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from metrics import default_run_usage

class RunStatus(str, Enum):
    NOT_STARTED = "not_started"
    PLANNING = "planning"
    BUILDING = "building"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass
class RoundState:
    round_number: int
    sprint_contract_json_path: str | None = None
    builder_report_path: str | None = None
    evaluator_report_json_path: str | None = None
    evaluator_report_md_path: str | None = None
    outcome: str | None = None
    blocking_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoundState":
        return cls(
            round_number=int(data.get("round_number", 0)),
            sprint_contract_json_path=data.get("sprint_contract_json_path"),
            builder_report_path=data.get("builder_report_path"),
            evaluator_report_json_path=data.get("evaluator_report_json_path"),
            evaluator_report_md_path=data.get("evaluator_report_md_path"),
            outcome=data.get("outcome"),
            blocking_issues=list(data.get("blocking_issues", [])),
        )


@dataclass
class RunState:
    status: RunStatus = RunStatus.NOT_STARTED
    planner_complete: bool = False
    current_round: int = 0
    max_rounds: int = 3
    completed: bool = False
    latest_summary: str = ""
    llm_usage: dict[str, Any] = field(default_factory=default_run_usage)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunState":
        return cls(
            status=RunStatus(data.get("status", RunStatus.NOT_STARTED.value)),
            planner_complete=bool(data.get("planner_complete", False)),
            current_round=int(data.get("current_round", 0)),
            max_rounds=int(data.get("max_rounds", 3)),
            completed=bool(data.get("completed", False)),
            latest_summary=str(data.get("latest_summary", "")),
            llm_usage=dict(data.get("llm_usage", default_run_usage())),
            created_at=str(data.get("created_at", datetime.now(timezone.utc).isoformat())),
            updated_at=str(data.get("updated_at", datetime.now(timezone.utc).isoformat())),
        )
