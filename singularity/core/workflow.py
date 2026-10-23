"""
Singularity — Workflow Engine (Fáze 18).

Chains multiple tasks into a sequential pipeline where each step's
task_template may reference prior step results via {{step_N_result}}
placeholders. Execution is driven by the existing TaskQueue.
"""
from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from core.task_queue import TaskQueue

log = structlog.get_logger()

_POLL_S = 0.2   # interval between queue polls while awaiting step completion


@dataclass
class WorkflowStep:
    step_id: str
    task_template: str   # may contain {{step_N_result}} placeholders
    user_id: str
    force_provider: str = ""
    priority: str = "NORMAL"
    max_retries: int = 0

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "task_template": self.task_template,
            "user_id": self.user_id,
            "force_provider": self.force_provider,
            "priority": self.priority,
            "max_retries": self.max_retries,
        }


@dataclass
class Workflow:
    workflow_id: str
    name: str
    steps: list[WorkflowStep]
    status: str = "pending"          # pending | running | completed | failed
    current_step: int = 0
    results: list[dict] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "step_count": len(self.steps),
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status,
            "current_step": self.current_step,
            "results": self.results,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "error": self.error,
        }


class WorkflowEngine:
    """
    Creates and runs sequential multi-step workflows via the TaskQueue.
    run_workflow() is a coroutine; call it inside asyncio.create_task() for
    non-blocking execution from a FastAPI endpoint.
    """

    def __init__(self) -> None:
        self._workflows: dict[str, Workflow] = {}
        self._lock = threading.Lock()

    def create_workflow(self, name: str, steps: list[dict]) -> str:
        if not steps:
            raise ValueError("Workflow must contain at least one step")
        workflow_id = str(uuid.uuid4())
        parsed: list[WorkflowStep] = []
        for s in steps:
            parsed.append(WorkflowStep(
                step_id=str(uuid.uuid4()),
                task_template=s.get("task", s.get("task_template", "")),
                user_id=s.get("user_id", "workflow"),
                force_provider=s.get("force_provider", ""),
                priority=s.get("priority", "NORMAL"),
                max_retries=s.get("max_retries", 0),
            ))
        wf = Workflow(workflow_id=workflow_id, name=name, steps=parsed)
        with self._lock:
            self._workflows[workflow_id] = wf
        log.info("workflow_created", workflow_id=workflow_id, steps=len(parsed))
        return workflow_id

    def get_workflow(self, workflow_id: str) -> dict | None:
        with self._lock:
            wf = self._workflows.get(workflow_id)
        return wf.to_dict() if wf else None

    def list_workflows(self) -> list[dict]:
        with self._lock:
            items = list(self._workflows.values())
        return [wf.to_dict() for wf in items]

    def workflow_count(self) -> int:
        with self._lock:
            return len(self._workflows)

    async def run_workflow(self, workflow_id: str, queue: TaskQueue) -> dict:
        """Execute all steps sequentially. Returns the final step result dict."""
        with self._lock:
            wf = self._workflows.get(workflow_id)
        if wf is None:
            raise KeyError(f"No workflow: {workflow_id!r}")
        if wf.status == "running":
            raise RuntimeError(f"Workflow {workflow_id!r} is already running")

        with self._lock:
            wf.status = "running"
            wf.current_step = 0
            wf.results = []
            wf.error = None

        log.info("workflow_started", workflow_id=workflow_id, steps=len(wf.steps))
        try:
            for i, step in enumerate(wf.steps):
                task_text = _resolve_template(step.task_template, wf.results)
                task_id = await queue.submit(
                    task=task_text,
                    user_id=step.user_id,
                    force_provider=step.force_provider,
                    priority=step.priority,
                    max_retries=step.max_retries,
                )
                with self._lock:
                    wf.current_step = i
                result = await _poll_until_done(queue, task_id)
                with self._lock:
                    wf.results.append(result)
                log.info("workflow_step_done", workflow_id=workflow_id, step=i, task_id=task_id)

            with self._lock:
                wf.status = "completed"
                wf.completed_at = datetime.now(timezone.utc).isoformat()
            log.info("workflow_completed", workflow_id=workflow_id)
            return wf.results[-1] if wf.results else {}

        except Exception as exc:
            with self._lock:
                wf.status = "failed"
                wf.error = str(exc)
                wf.completed_at = datetime.now(timezone.utc).isoformat()
            log.error("workflow_failed", workflow_id=workflow_id, error=str(exc))
            raise


def _resolve_template(template: str, results: list[dict]) -> str:
    """Replace {{step_N_result}} placeholders with prior step responses."""
    for i, res in enumerate(results):
        value = str(res.get("response", res.get("result", "")))
        template = template.replace(f"{{{{step_{i}_result}}}}", value)
    return template


async def _poll_until_done(queue: TaskQueue, task_id: str, timeout: float = 120.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        status = queue.get_status(task_id)
        if status is not None and status.get("status") in ("completed", "failed", "dlq"):
            result = queue.get_result(task_id)
            return result if result is not None else status
        if asyncio.get_event_loop().time() >= deadline:
            raise TimeoutError(f"Task {task_id!r} did not finish within {timeout}s")
        await asyncio.sleep(_POLL_S)
