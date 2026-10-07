"""
Singularity — Multi-Agent Orchestrator (Fáze 28).

Supervisor-worker orchestration with DAG-based dependency resolution, parallel
wave execution, upstream result injection, and pluggable aggregation strategies.

Fully offline-compatible: providers are injected as async callables, enabling
deterministic unit testing without any external dependencies.
"""
from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine

import structlog

log = structlog.get_logger()


# ── Enums ─────────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class AggregationStrategy(str, Enum):
    MERGE = "merge"              # "\n\n".join all results
    SELECT_BEST = "select_best"  # longest result (proxy for richness)
    VOTE = "vote"                # majority vote (exact match)


# ── Exceptions ────────────────────────────────────────────────────────────────

class DependencyError(ValueError):
    """Raised when a DAG has unknown dependency IDs or cycles."""


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class AgentTask:
    task_id: str
    prompt: str
    provider: str | None = None
    depends_on: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: str | None = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "prompt": self.prompt,
            "provider": self.provider,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass
class ExecutionPlan:
    plan_id: str
    tasks: list[AgentTask]
    aggregation: AggregationStrategy
    created_at: str
    status: str = "pending"

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "aggregation": self.aggregation.value,
            "created_at": self.created_at,
            "status": self.status,
            "task_count": len(self.tasks),
            "tasks": [t.to_dict() for t in self.tasks],
        }


@dataclass
class OrchestrationResult:
    plan_id: str
    final_output: str
    aggregation: AggregationStrategy
    task_results: list[dict]
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    skipped_tasks: int
    duration_ms: float

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "final_output": self.final_output,
            "aggregation": self.aggregation.value,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "skipped_tasks": self.skipped_tasks,
            "duration_ms": self.duration_ms,
            "task_results": self.task_results,
        }


# ── Provider type alias ───────────────────────────────────────────────────────

ProviderFn = Callable[[str, str | None], Coroutine[Any, Any, str]]


# ── Orchestrator ──────────────────────────────────────────────────────────────

class MultiAgentOrchestrator:
    """
    Supervisor-worker orchestrator for multi-agent task execution.

    Usage:
        async def my_provider(prompt, provider_name):
            return "answer"

        orc = MultiAgentOrchestrator(router=my_provider, max_parallel=4)
        plan = orc.create_plan([
            {"task_id": "t1", "prompt": "Analyze X"},
            {"task_id": "t2", "prompt": "Summarize {{t1}}", "depends_on": ["t1"]},
        ])
        result = await orc.execute(plan)
    """

    def __init__(
        self,
        router: ProviderFn | None = None,
        *,
        max_parallel: int = 8,
        timeout_s: float = 60.0,
    ) -> None:
        if max_parallel < 1:
            raise ValueError("max_parallel must be >= 1")
        if timeout_s <= 0:
            raise ValueError("timeout_s must be > 0")
        self._router = router
        self.max_parallel = max_parallel
        self.timeout_s = timeout_s
        self._lock = threading.Lock()
        self._total_plans = 0
        self._total_tasks_executed = 0
        self._tasks_failed = 0
        self._tasks_skipped = 0
        self._wave_counts: list[int] = []
        self._plans_with_failures = 0

    # ── Plan creation ─────────────────────────────────────────────────────────

    def create_plan(
        self,
        tasks: list[dict],
        aggregation: str = "merge",
    ) -> ExecutionPlan:
        """
        Validate task list and return an ExecutionPlan.

        Raises ValueError / DependencyError for:
          - empty task list
          - task with empty prompt
          - depends_on referencing unknown task_id
          - cyclic dependency
          - invalid aggregation strategy
        """
        if not tasks:
            raise ValueError("tasks must not be empty")
        try:
            agg = AggregationStrategy(aggregation)
        except ValueError:
            raise ValueError(
                f"aggregation must be one of {[a.value for a in AggregationStrategy]}"
            )

        agent_tasks: list[AgentTask] = []
        ids_seen: set[str] = set()

        for raw in tasks:
            tid = str(raw.get("task_id") or uuid.uuid4())
            prompt = str(raw.get("prompt") or "").strip()
            if not prompt:
                raise ValueError(f"task '{tid}' has an empty prompt")
            deps = list(raw.get("depends_on") or [])
            agent_tasks.append(AgentTask(
                task_id=tid,
                prompt=prompt,
                provider=raw.get("provider"),
                depends_on=deps,
            ))
            ids_seen.add(tid)

        for t in agent_tasks:
            for dep in t.depends_on:
                if dep not in ids_seen:
                    raise DependencyError(
                        f"task '{t.task_id}' depends_on unknown task_id '{dep}'"
                    )

        self._detect_cycle(agent_tasks)

        return ExecutionPlan(
            plan_id=str(uuid.uuid4()),
            tasks=agent_tasks,
            aggregation=agg,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def _detect_cycle(self, tasks: list[AgentTask]) -> None:
        """Kahn's algorithm — raises DependencyError if a cycle exists."""
        in_degree = {t.task_id: len(t.depends_on) for t in tasks}
        dependents: dict[str, list[str]] = {t.task_id: [] for t in tasks}
        for t in tasks:
            for dep in t.depends_on:
                dependents[dep].append(t.task_id)

        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        visited = 0
        while queue:
            node = queue.pop(0)
            visited += 1
            for child in dependents[node]:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if visited != len(tasks):
            raise DependencyError("circular dependency detected in task graph")

    # ── Execution ─────────────────────────────────────────────────────────────

    async def execute(self, plan: ExecutionPlan) -> OrchestrationResult:
        """
        Execute plan wave-by-wave:
        1. Group tasks into parallel waves via topological sort
        2. asyncio.gather each wave (bounded by max_parallel semaphore)
        3. Failed/skipped deps propagate as SKIPPED to downstream tasks
        4. Aggregate done results → final_output
        """
        import time
        start = time.monotonic()

        plan.status = "running"
        task_map: dict[str, AgentTask] = {t.task_id: t for t in plan.tasks}
        waves = self._topological_waves(plan.tasks)
        context: dict[str, str] = {}
        has_failure = False

        sem = asyncio.Semaphore(self.max_parallel)

        for wave in waves:
            runnable: list[AgentTask] = []
            for task in wave:
                should_skip = any(
                    task_map[dep].status in (TaskStatus.FAILED, TaskStatus.SKIPPED)
                    for dep in task.depends_on
                    if dep in task_map
                )
                if should_skip:
                    task.status = TaskStatus.SKIPPED
                    with self._lock:
                        self._tasks_skipped += 1
                else:
                    runnable.append(task)

            async def _bounded(t: AgentTask, _sem: asyncio.Semaphore = sem) -> AgentTask:
                async with _sem:
                    return await self._run_task(t, context)

            executed = await asyncio.gather(*[_bounded(t) for t in runnable])

            for task in executed:
                task_map[task.task_id] = task
                if task.status == TaskStatus.DONE and task.result is not None:
                    context[task.task_id] = task.result
                elif task.status == TaskStatus.FAILED:
                    has_failure = True

        done_tasks = [t for t in task_map.values() if t.status == TaskStatus.DONE]
        failed_tasks = [t for t in task_map.values() if t.status == TaskStatus.FAILED]
        skipped_tasks = [t for t in task_map.values() if t.status == TaskStatus.SKIPPED]

        final_output = self._aggregate(done_tasks, plan.aggregation)
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        plan.status = "partial" if failed_tasks else "done"

        with self._lock:
            self._total_plans += 1
            self._total_tasks_executed += len(done_tasks) + len(failed_tasks)
            self._wave_counts.append(len(waves))
            if has_failure:
                self._plans_with_failures += 1

        log.info(
            "orchestration_complete",
            plan_id=plan.plan_id,
            done=len(done_tasks),
            failed=len(failed_tasks),
            skipped=len(skipped_tasks),
            duration_ms=duration_ms,
        )

        return OrchestrationResult(
            plan_id=plan.plan_id,
            final_output=final_output,
            aggregation=plan.aggregation,
            task_results=[t.to_dict() for t in task_map.values()],
            total_tasks=len(task_map),
            completed_tasks=len(done_tasks),
            failed_tasks=len(failed_tasks),
            skipped_tasks=len(skipped_tasks),
            duration_ms=duration_ms,
        )

    def _topological_waves(self, tasks: list[AgentTask]) -> list[list[AgentTask]]:
        """Kahn's algorithm → list of parallel execution waves."""
        task_map = {t.task_id: t for t in tasks}
        in_degree = {t.task_id: len(t.depends_on) for t in tasks}
        dependents: dict[str, list[str]] = {t.task_id: [] for t in tasks}
        for t in tasks:
            for dep in t.depends_on:
                dependents[dep].append(t.task_id)

        waves: list[list[AgentTask]] = []
        ready = [t for t in tasks if in_degree[t.task_id] == 0]

        while ready:
            waves.append(list(ready))
            next_ready: list[AgentTask] = []
            for t in ready:
                for child_id in dependents[t.task_id]:
                    in_degree[child_id] -= 1
                    if in_degree[child_id] == 0:
                        next_ready.append(task_map[child_id])
            ready = next_ready

        return waves

    async def _run_task(self, task: AgentTask, context: dict[str, str]) -> AgentTask:
        """
        Execute one task: substitute upstream placeholders, call provider,
        apply timeout, record status and timestamps.
        """
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc).isoformat()

        prompt = task.prompt
        for tid, res in context.items():
            prompt = prompt.replace(f"{{{{{tid}}}}}", res)

        try:
            if self._router is None:
                raise RuntimeError("No provider configured for MultiAgentOrchestrator")
            result = await asyncio.wait_for(
                self._router(prompt, task.provider),
                timeout=self.timeout_s,
            )
            task.result = result
            task.status = TaskStatus.DONE
        except asyncio.TimeoutError:
            task.status = TaskStatus.FAILED
            task.error = f"timeout after {self.timeout_s}s"
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)

        task.finished_at = datetime.now(timezone.utc).isoformat()
        return task

    # ── Aggregation ───────────────────────────────────────────────────────────

    def _aggregate(self, done_tasks: list[AgentTask], strategy: AggregationStrategy) -> str:
        results = [t.result for t in done_tasks if t.result]
        if not results:
            return ""

        if strategy == AggregationStrategy.MERGE:
            return "\n\n".join(results)

        if strategy == AggregationStrategy.SELECT_BEST:
            return max(results, key=len)

        if strategy == AggregationStrategy.VOTE:
            from collections import Counter
            winner, _ = Counter(results).most_common(1)[0]
            return winner

        return "\n\n".join(results)

    # ── Metrics ───────────────────────────────────────────────────────────────

    def metrics(self) -> dict:
        with self._lock:
            avg_waves = (
                sum(self._wave_counts) / len(self._wave_counts)
                if self._wave_counts else 0.0
            )
            return {
                "total_plans": self._total_plans,
                "total_tasks_executed": self._total_tasks_executed,
                "tasks_failed": self._tasks_failed,
                "tasks_skipped": self._tasks_skipped,
                "avg_wave_count": round(avg_waves, 2),
                "plans_with_failures": self._plans_with_failures,
            }

    def reset_metrics(self) -> None:
        with self._lock:
            self._total_plans = 0
            self._total_tasks_executed = 0
            self._tasks_failed = 0
            self._tasks_skipped = 0
            self._wave_counts = []
            self._plans_with_failures = 0
