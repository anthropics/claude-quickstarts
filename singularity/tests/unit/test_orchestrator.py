"""
Tests for MultiAgentOrchestrator (Fáze 28).
All offline — provider mocked as AsyncMock, no external dependencies.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock

from core.orchestrator import (
    MultiAgentOrchestrator,
    AgentTask,
    AggregationStrategy,
    TaskStatus,
    DependencyError,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_orc(response: str = "result", fail: bool = False,
              max_parallel: int = 4, timeout_s: float = 5.0) -> MultiAgentOrchestrator:
    if fail:
        provider = AsyncMock(side_effect=RuntimeError("provider error"))
    else:
        provider = AsyncMock(return_value=response)
    return MultiAgentOrchestrator(router=provider, max_parallel=max_parallel,
                                  timeout_s=timeout_s)


# ── Constructor validation ─────────────────────────────────────────────────────

def test_invalid_max_parallel_raises():
    with pytest.raises(ValueError, match="max_parallel"):
        MultiAgentOrchestrator(router=AsyncMock(), max_parallel=0)


def test_invalid_timeout_raises():
    with pytest.raises(ValueError, match="timeout_s"):
        MultiAgentOrchestrator(router=AsyncMock(), timeout_s=0.0)


def test_valid_construction():
    orc = MultiAgentOrchestrator(router=AsyncMock(), max_parallel=2, timeout_s=10.0)
    assert orc.max_parallel == 2
    assert orc.timeout_s == 10.0


# ── Plan creation — validation ─────────────────────────────────────────────────

def test_create_plan_empty_tasks_raises():
    orc = _make_orc()
    with pytest.raises(ValueError, match="empty"):
        orc.create_plan([])


def test_create_plan_empty_prompt_raises():
    orc = _make_orc()
    with pytest.raises(ValueError, match="empty prompt"):
        orc.create_plan([{"task_id": "t1", "prompt": "   "}])


def test_create_plan_unknown_dep_raises():
    orc = _make_orc()
    with pytest.raises(DependencyError, match="unknown task_id"):
        orc.create_plan([
            {"task_id": "t1", "prompt": "hello", "depends_on": ["ghost"]},
        ])


def test_create_plan_cycle_raises():
    orc = _make_orc()
    with pytest.raises(DependencyError, match="circular"):
        orc.create_plan([
            {"task_id": "t1", "prompt": "a", "depends_on": ["t2"]},
            {"task_id": "t2", "prompt": "b", "depends_on": ["t1"]},
        ])


def test_create_plan_invalid_aggregation_raises():
    orc = _make_orc()
    with pytest.raises(ValueError, match="aggregation"):
        orc.create_plan([{"task_id": "t1", "prompt": "x"}], aggregation="nuke")


def test_create_plan_valid_returns_plan():
    orc = _make_orc()
    plan = orc.create_plan([{"task_id": "t1", "prompt": "hello"}])
    assert plan.plan_id
    assert len(plan.tasks) == 1
    assert plan.tasks[0].task_id == "t1"
    assert plan.aggregation == AggregationStrategy.MERGE


# ── Topological waves ─────────────────────────────────────────────────────────

def test_single_task_produces_one_wave():
    orc = _make_orc()
    tasks = [AgentTask("t1", "hello")]
    waves = orc._topological_waves(tasks)
    assert len(waves) == 1
    assert waves[0][0].task_id == "t1"


def test_independent_tasks_same_wave():
    orc = _make_orc()
    tasks = [AgentTask("t1", "a"), AgentTask("t2", "b"), AgentTask("t3", "c")]
    waves = orc._topological_waves(tasks)
    assert len(waves) == 1
    assert len(waves[0]) == 3


def test_linear_chain_three_waves():
    orc = _make_orc()
    tasks = [
        AgentTask("t1", "a"),
        AgentTask("t2", "b", depends_on=["t1"]),
        AgentTask("t3", "c", depends_on=["t2"]),
    ]
    waves = orc._topological_waves(tasks)
    assert len(waves) == 3
    assert waves[0][0].task_id == "t1"
    assert waves[1][0].task_id == "t2"
    assert waves[2][0].task_id == "t3"


def test_diamond_dependency_two_waves():
    tasks = [
        AgentTask("t1", "root"),
        AgentTask("t2", "left", depends_on=["t1"]),
        AgentTask("t3", "right", depends_on=["t1"]),
        AgentTask("t4", "merge", depends_on=["t2", "t3"]),
    ]
    orc = _make_orc()
    waves = orc._topological_waves(tasks)
    assert len(waves) == 3
    wave_ids = [set(t.task_id for t in w) for w in waves]
    assert wave_ids[0] == {"t1"}
    assert wave_ids[1] == {"t2", "t3"}
    assert wave_ids[2] == {"t4"}


# ── Execution ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_single_task_done():
    orc = _make_orc(response="answer42")
    plan = orc.create_plan([{"task_id": "t1", "prompt": "What is 6*7?"}])
    result = await orc.execute(plan)
    assert result.completed_tasks == 1
    assert result.failed_tasks == 0
    assert result.final_output == "answer42"


@pytest.mark.asyncio
async def test_execute_parallel_tasks_all_done():
    orc = _make_orc(response="ok")
    plan = orc.create_plan([
        {"task_id": "t1", "prompt": "task one"},
        {"task_id": "t2", "prompt": "task two"},
        {"task_id": "t3", "prompt": "task three"},
    ])
    result = await orc.execute(plan)
    assert result.completed_tasks == 3
    assert result.failed_tasks == 0
    assert result.skipped_tasks == 0


@pytest.mark.asyncio
async def test_execute_chain_result_propagation():
    call_log: list[str] = []

    async def provider(prompt: str, _: str | None) -> str:
        call_log.append(prompt)
        return "UPSTREAM"

    orc = MultiAgentOrchestrator(router=provider, max_parallel=2, timeout_s=5.0)
    plan = orc.create_plan([
        {"task_id": "t1", "prompt": "base"},
        {"task_id": "t2", "prompt": "after {{t1}} do more", "depends_on": ["t1"]},
    ])
    await orc.execute(plan)
    assert "{{t1}}" not in call_log[1]
    assert "UPSTREAM" in call_log[1]


@pytest.mark.asyncio
async def test_execute_failed_task_skips_downstream():
    orc = _make_orc(fail=True)
    plan = orc.create_plan([
        {"task_id": "t1", "prompt": "root"},
        {"task_id": "t2", "prompt": "child", "depends_on": ["t1"]},
    ])
    result = await orc.execute(plan)
    assert result.failed_tasks == 1
    assert result.skipped_tasks == 1
    assert result.completed_tasks == 0


@pytest.mark.asyncio
async def test_execute_partial_failure_still_returns_result():
    call_count = 0

    async def flaky(prompt: str, _: str | None) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("first task fails")
        return "good result"

    orc = MultiAgentOrchestrator(router=flaky, max_parallel=2, timeout_s=5.0)
    plan = orc.create_plan([
        {"task_id": "t1", "prompt": "will fail"},
        {"task_id": "t2", "prompt": "will succeed"},
    ])
    result = await orc.execute(plan)
    assert result.completed_tasks == 1
    assert result.failed_tasks == 1
    assert result.final_output == "good result"


@pytest.mark.asyncio
async def test_execute_task_timeout_marks_failed():
    async def slow(prompt: str, _: str | None) -> str:
        await asyncio.sleep(10)
        return "too late"

    orc = MultiAgentOrchestrator(router=slow, max_parallel=1, timeout_s=0.05)
    plan = orc.create_plan([{"task_id": "t1", "prompt": "slow task"}])
    result = await orc.execute(plan)
    assert result.failed_tasks == 1
    assert result.completed_tasks == 0
    tr = result.task_results[0]
    assert "timeout" in (tr["error"] or "")


# ── Aggregation ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_aggregate_merge_joins_results():
    responses = ["part A", "part B", "part C"]
    idx = 0

    async def provider(prompt: str, _: str | None) -> str:
        nonlocal idx
        r = responses[idx % len(responses)]
        idx += 1
        return r

    orc = MultiAgentOrchestrator(router=provider, max_parallel=4, timeout_s=5.0)
    plan = orc.create_plan(
        [{"task_id": f"t{i}", "prompt": f"p{i}"} for i in range(3)],
        aggregation="merge",
    )
    result = await orc.execute(plan)
    for part in responses:
        assert part in result.final_output


@pytest.mark.asyncio
async def test_aggregate_select_best_picks_longest():
    short = "short"
    long_ = "this is a much longer result that should win the selection"

    async def provider(prompt: str, _: str | None) -> str:
        return short if "t1" in prompt else long_

    orc = MultiAgentOrchestrator(router=provider, max_parallel=4, timeout_s=5.0)
    plan = orc.create_plan(
        [{"task_id": "t1", "prompt": "t1"}, {"task_id": "t2", "prompt": "t2"}],
        aggregation="select_best",
    )
    result = await orc.execute(plan)
    assert result.final_output == long_


@pytest.mark.asyncio
async def test_aggregate_vote_majority_wins():
    responses = ["answer_A", "answer_A", "answer_B"]
    idx = 0

    async def provider(prompt: str, _: str | None) -> str:
        nonlocal idx
        r = responses[idx % len(responses)]
        idx += 1
        return r

    orc = MultiAgentOrchestrator(router=provider, max_parallel=4, timeout_s=5.0)
    plan = orc.create_plan(
        [{"task_id": f"t{i}", "prompt": f"p{i}"} for i in range(3)],
        aggregation="vote",
    )
    result = await orc.execute(plan)
    assert result.final_output == "answer_A"


@pytest.mark.asyncio
async def test_aggregate_vote_tie_returns_a_valid_answer():
    responses = ["alpha", "beta"]
    idx = 0

    async def provider(prompt: str, _: str | None) -> str:
        nonlocal idx
        r = responses[idx % len(responses)]
        idx += 1
        return r

    orc = MultiAgentOrchestrator(router=provider, max_parallel=4, timeout_s=5.0)
    plan = orc.create_plan(
        [{"task_id": "t1", "prompt": "a"}, {"task_id": "t2", "prompt": "b"}],
        aggregation="vote",
    )
    result = await orc.execute(plan)
    assert result.final_output in ("alpha", "beta")


# ── OrchestrationResult ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_result_counts_completed_failed_skipped():
    call_count = 0

    async def mixed(prompt: str, _: str | None) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("fail")
        return "ok"

    orc = MultiAgentOrchestrator(router=mixed, max_parallel=4, timeout_s=5.0)
    plan = orc.create_plan([
        {"task_id": "t1", "prompt": "fail"},
        {"task_id": "t2", "prompt": "ok"},
        {"task_id": "t3", "prompt": "skip", "depends_on": ["t1"]},
    ])
    result = await orc.execute(plan)
    assert result.total_tasks == 3
    assert result.completed_tasks == 1
    assert result.failed_tasks == 1
    assert result.skipped_tasks == 1


@pytest.mark.asyncio
async def test_result_duration_ms_non_negative():
    orc = _make_orc()
    plan = orc.create_plan([{"task_id": "t1", "prompt": "quick"}])
    result = await orc.execute(plan)
    assert result.duration_ms >= 0.0


@pytest.mark.asyncio
async def test_result_to_dict_shape():
    orc = _make_orc(response="hello")
    plan = orc.create_plan([{"task_id": "t1", "prompt": "p"}])
    result = await orc.execute(plan)
    d = result.to_dict()
    for key in ("plan_id", "final_output", "aggregation", "total_tasks",
                "completed_tasks", "failed_tasks", "skipped_tasks",
                "duration_ms", "task_results"):
        assert key in d


# ── Metrics ───────────────────────────────────────────────────────────────────

def test_metrics_initial_zeros():
    orc = _make_orc()
    m = orc.metrics()
    assert m["total_plans"] == 0
    assert m["total_tasks_executed"] == 0
    assert m["tasks_failed"] == 0
    assert m["tasks_skipped"] == 0
    assert m["plans_with_failures"] == 0


@pytest.mark.asyncio
async def test_metrics_after_execution():
    orc = _make_orc(response="done")
    plan = orc.create_plan([
        {"task_id": "t1", "prompt": "a"},
        {"task_id": "t2", "prompt": "b"},
    ])
    await orc.execute(plan)
    m = orc.metrics()
    assert m["total_plans"] == 1
    assert m["total_tasks_executed"] == 2
    assert m["avg_wave_count"] == 1.0


@pytest.mark.asyncio
async def test_metrics_plans_with_failures():
    orc = _make_orc(fail=True)
    plan = orc.create_plan([{"task_id": "t1", "prompt": "x"}])
    await orc.execute(plan)
    m = orc.metrics()
    assert m["plans_with_failures"] == 1


@pytest.mark.asyncio
async def test_metrics_reset():
    orc = _make_orc(response="ok")
    plan = orc.create_plan([{"task_id": "t1", "prompt": "x"}])
    await orc.execute(plan)
    orc.reset_metrics()
    m = orc.metrics()
    assert m["total_plans"] == 0
    assert m["total_tasks_executed"] == 0


# ── Edge cases ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_string_result_aggregates_to_empty():
    orc = MultiAgentOrchestrator(router=AsyncMock(return_value=""), max_parallel=2,
                                  timeout_s=5.0)
    plan = orc.create_plan([{"task_id": "t1", "prompt": "p"}])
    result = await orc.execute(plan)
    assert result.final_output == ""


@pytest.mark.asyncio
async def test_placeholder_substitution():
    async def provider(prompt: str, _: str | None) -> str:
        if prompt == "base":
            return "BASE_OUTPUT"
        return prompt  # echo the (substituted) prompt back

    orc = MultiAgentOrchestrator(router=provider, max_parallel=2, timeout_s=5.0)
    plan = orc.create_plan([
        {"task_id": "root", "prompt": "base"},
        {"task_id": "child", "prompt": "prefix {{root}} suffix", "depends_on": ["root"]},
    ])
    result = await orc.execute(plan)
    child_result = next(t["result"] for t in result.task_results if t["task_id"] == "child")
    assert child_result == "prefix BASE_OUTPUT suffix"


@pytest.mark.asyncio
async def test_no_router_configured_fails_task():
    orc = MultiAgentOrchestrator(router=None, max_parallel=2, timeout_s=5.0)
    plan = orc.create_plan([{"task_id": "t1", "prompt": "x"}])
    result = await orc.execute(plan)
    assert result.failed_tasks == 1


@pytest.mark.asyncio
async def test_execution_plan_to_dict():
    orc = _make_orc()
    plan = orc.create_plan([
        {"task_id": "t1", "prompt": "hello"},
        {"task_id": "t2", "prompt": "world", "depends_on": ["t1"]},
    ])
    d = plan.to_dict()
    assert d["task_count"] == 2
    assert d["aggregation"] == "merge"
    assert len(d["tasks"]) == 2
