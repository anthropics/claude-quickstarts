"""
Tests for WorkflowEngine (Fáze 18).
All offline — TaskQueue is replaced by a lightweight mock.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from core.workflow import WorkflowEngine, _resolve_template


@pytest.fixture
def engine():
    return WorkflowEngine()


def _make_queue(responses: list[str]) -> MagicMock:
    """Build a mock TaskQueue that returns successive responses."""
    call_count = {"n": 0}

    def _get_status(task_id):
        return {"status": "completed"}

    def _get_result(task_id):
        idx = int(task_id.split("-")[1])
        return {"response": responses[idx]}

    q = MagicMock()
    q.submit = AsyncMock(side_effect=lambda **kw: f"task-{call_count['n']:=count}")
    # simpler: sequential task IDs
    task_ids = [f"task-{i}" for i in range(len(responses))]
    q.submit = AsyncMock(side_effect=task_ids)
    q.get_status = MagicMock(side_effect=_get_status)
    q.get_result = MagicMock(side_effect=_get_result)
    return q


# ── Creation ──────────────────────────────────────────────────────────────────

def test_create_workflow_returns_id(engine):
    wid = engine.create_workflow("test", [{"task": "Do A"}])
    assert wid is not None
    assert len(wid) == 36


def test_create_empty_steps_raises(engine):
    with pytest.raises(ValueError):
        engine.create_workflow("empty", [])


def test_workflow_count(engine):
    engine.create_workflow("wf1", [{"task": "A"}])
    engine.create_workflow("wf2", [{"task": "B"}])
    assert engine.workflow_count() == 2


# ── Retrieval ─────────────────────────────────────────────────────────────────

def test_get_workflow_returns_dict(engine):
    wid = engine.create_workflow("myflow", [{"task": "Step 1"}])
    wf = engine.get_workflow(wid)
    assert wf is not None
    assert wf["name"] == "myflow"
    assert wf["step_count"] == 1
    assert wf["status"] == "pending"


def test_get_workflow_missing_returns_none(engine):
    assert engine.get_workflow("no-such-id") is None


def test_list_workflows_empty(engine):
    assert engine.list_workflows() == []


def test_list_workflows_contains_created(engine):
    engine.create_workflow("alpha", [{"task": "A"}])
    engine.create_workflow("beta", [{"task": "B"}])
    names = {wf["name"] for wf in engine.list_workflows()}
    assert names == {"alpha", "beta"}


# ── Template resolution ───────────────────────────────────────────────────────

def test_resolve_template_no_placeholders():
    assert _resolve_template("hello world", []) == "hello world"


def test_resolve_template_substitutes_step_0():
    results = [{"response": "Paris"}]
    out = _resolve_template("Capital is {{step_0_result}}", results)
    assert out == "Capital is Paris"


def test_resolve_template_multi_step():
    results = [{"response": "3"}, {"response": "7"}]
    out = _resolve_template("{{step_0_result}} + {{step_1_result}}", results)
    assert out == "3 + 7"


def test_resolve_template_missing_placeholder_untouched():
    out = _resolve_template("{{step_5_result}}", [])
    assert out == "{{step_5_result}}"


# ── Execution ─────────────────────────────────────────────────────────────────

async def test_run_single_step(engine):
    q = _make_queue(["Answer A"])
    wid = engine.create_workflow("single", [{"task": "What is A?"}])
    result = await engine.run_workflow(wid, q)
    assert result["response"] == "Answer A"
    wf = engine.get_workflow(wid)
    assert wf["status"] == "completed"
    assert wf["completed_at"] is not None


async def test_run_multi_step_chains_result(engine):
    q = _make_queue(["42", "The answer is 42"])
    wid = engine.create_workflow("chain", [
        {"task": "Give me a number"},
        {"task": "Explain: {{step_0_result}}"},
    ])
    result = await engine.run_workflow(wid, q)
    assert result["response"] == "The answer is 42"
    # Second submit call should have received the resolved template
    second_call_kwargs = q.submit.call_args_list[1].kwargs
    assert second_call_kwargs["task"] == "Explain: 42"


async def test_run_already_running_raises(engine):
    wid = engine.create_workflow("running", [{"task": "A"}])
    wf_obj = engine._workflows[wid]
    wf_obj.status = "running"
    with pytest.raises(RuntimeError, match="already running"):
        await engine.run_workflow(wid, MagicMock())


async def test_run_missing_workflow_raises(engine):
    with pytest.raises(KeyError):
        await engine.run_workflow("ghost-id", MagicMock())


async def test_run_queue_error_marks_failed(engine):
    q = MagicMock()
    q.submit = AsyncMock(side_effect=RuntimeError("queue down"))
    wid = engine.create_workflow("fail", [{"task": "A"}])
    with pytest.raises(RuntimeError, match="queue down"):
        await engine.run_workflow(wid, q)
    wf = engine.get_workflow(wid)
    assert wf["status"] == "failed"
    assert "queue down" in wf["error"]
