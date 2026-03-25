from __future__ import annotations

import asyncio
import json
from pathlib import Path

from orchestrator import ModelConfig, Orchestrator




class DummyClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def dummy_client_factory(project_dir: Path, model: str, phase: str):
    del project_dir, model, phase
    return DummyClient()


class FakeRunner:
    def __init__(self, project_dir: Path, outcomes: list[str]):
        self.project_dir = project_dir
        self.outcomes = outcomes
        self.eval_calls = 0
        self.planner_calls = 0
        self.builder_calls = 0
        self.clients_by_phase: dict[str, list[object | None]] = {"planner": [], "builder": [], "evaluator": []}

    async def __call__(
        self,
        project_dir: Path,
        model: str,
        prompt: str,
        phase: str,
        client=None,
    ) -> str:
        del model, prompt
        if phase == "planner":
            self.planner_calls += 1
            planning = project_dir / "planning"
            planning.mkdir(parents=True, exist_ok=True)
            (planning / "expanded_spec.md").write_text("# Expanded\n")
            (planning / "architecture.md").write_text("# Architecture\n")
            (planning / "acceptance_criteria.json").write_text(
                json.dumps(
                    {
                        "project_name": "demo",
                        "criteria": [{"id": "AC-1", "description": "d", "priority": "p0"}],
                    }
                )
            )
            (planning / "work_backlog.json").write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "id": "WB-1",
                                "title": "t",
                                "status": "todo",
                                "source_feature_index": 0,
                            }
                        ]
                    }
                )
            )

        if phase == "builder":
            self.builder_calls += 1

        if phase == "evaluator":
            self.eval_calls += 1
            outcome = self.outcomes[min(self.eval_calls - 1, len(self.outcomes) - 1)]
            qa = project_dir / "qa"
            qa.mkdir(parents=True, exist_ok=True)
            qa_report = {
                "round": self.eval_calls,
                "result": outcome,
                "summary": f"round {self.eval_calls} => {outcome}",
                "blocking_findings": []
                if outcome == "pass"
                else [
                    {
                        "id": f"Q-{self.eval_calls}",
                        "severity": "high",
                        "description": "issue",
                        "repro_steps": ["do x"],
                    }
                ],
            }
            (qa / f"qa_report_round_{self.eval_calls:02d}.json").write_text(json.dumps(qa_report))

        if phase in self.clients_by_phase:
            self.clients_by_phase[phase].append(client)
        return f"fake {phase}"


def test_first_run_then_complete(tmp_path: Path) -> None:
    runner = FakeRunner(tmp_path, ["pass"])
    orchestrator = Orchestrator(
        project_dir=tmp_path,
        model_config=ModelConfig("m", "m", "m"),
        max_rounds=2,
        phase_runner=runner,
        client_factory=dummy_client_factory,
    )
    state = asyncio.run(orchestrator.run(resume=False))
    assert state.completed is True
    assert state.current_round == 1
    assert (tmp_path / "planning" / "sprint_contract_round_01.json").exists()


def test_retry_loop_then_pass(tmp_path: Path) -> None:
    runner = FakeRunner(tmp_path, ["fail", "pass"])
    orchestrator = Orchestrator(
        project_dir=tmp_path,
        model_config=ModelConfig("m", "m", "m"),
        max_rounds=3,
        phase_runner=runner,
        client_factory=dummy_client_factory,
    )
    state = asyncio.run(orchestrator.run(resume=False))
    assert state.completed is True
    assert state.current_round == 2


def test_resume_skips_planner(tmp_path: Path) -> None:
    runner = FakeRunner(tmp_path, ["fail"])
    orchestrator = Orchestrator(
        project_dir=tmp_path,
        model_config=ModelConfig("m", "m", "m"),
        max_rounds=1,
        phase_runner=runner,
        client_factory=dummy_client_factory,
    )
    asyncio.run(orchestrator.run(resume=False))

    runner2 = FakeRunner(tmp_path, ["pass"])
    orchestrator2 = Orchestrator(
        project_dir=tmp_path,
        model_config=ModelConfig("m", "m", "m"),
        max_rounds=2,
        phase_runner=runner2,
        client_factory=dummy_client_factory,
    )
    state = asyncio.run(orchestrator2.run(resume=True, qa_only=True))
    assert state.current_round == 2
    assert runner2.planner_calls == 0
    assert runner2.eval_calls == 1


def test_resume_completed_run_does_not_restart(tmp_path: Path) -> None:
    runner = FakeRunner(tmp_path, ["pass"])
    orchestrator = Orchestrator(
        project_dir=tmp_path,
        model_config=ModelConfig("m", "m", "m"),
        max_rounds=2,
        phase_runner=runner,
        client_factory=dummy_client_factory,
    )
    asyncio.run(orchestrator.run(resume=False))

    runner2 = FakeRunner(tmp_path, ["fail"])
    orchestrator2 = Orchestrator(
        project_dir=tmp_path,
        model_config=ModelConfig("m", "m", "m"),
        max_rounds=2,
        phase_runner=runner2,
        client_factory=dummy_client_factory,
    )
    state = asyncio.run(orchestrator2.run(resume=True))
    assert state.completed is True
    assert runner2.planner_calls == 0
    assert runner2.eval_calls == 0


def test_builder_checkpoint_only_after_success(tmp_path: Path) -> None:
    class FailingBuilderRunner(FakeRunner):
        async def __call__(self, project_dir: Path, model: str, prompt: str, phase: str, client=None) -> str:
            if phase == "planner":
                return await super().__call__(project_dir, model, prompt, phase, client)
            if phase == "builder":
                raise RuntimeError("builder exploded")
            return await super().__call__(project_dir, model, prompt, phase, client)

    runner = FailingBuilderRunner(tmp_path, ["pass"])
    orchestrator = Orchestrator(
        project_dir=tmp_path,
        model_config=ModelConfig("m", "m", "m"),
        max_rounds=2,
        phase_runner=runner,
        client_factory=dummy_client_factory,
    )

    try:
        asyncio.run(orchestrator.run(resume=False))
    except RuntimeError:
        pass

    state = json.loads((tmp_path / "state" / "run_state.json").read_text())
    assert state["current_round"] == 0


def test_continuous_session_shares_client_object(tmp_path: Path) -> None:
    runner = FakeRunner(tmp_path, ["pass"])
    orchestrator = Orchestrator(
        project_dir=tmp_path,
        model_config=ModelConfig("m", "m", "m"),
        max_rounds=1,
        phase_runner=runner,
        client_factory=dummy_client_factory,
    )
    asyncio.run(orchestrator.run(resume=False))

    planner_client = runner.clients_by_phase["planner"][0]
    builder_client = runner.clients_by_phase["builder"][0]
    evaluator_client = runner.clients_by_phase["evaluator"][0]
    assert planner_client is builder_client is evaluator_client


def test_invalid_planner_only_and_qa_only_combination(tmp_path: Path) -> None:
    runner = FakeRunner(tmp_path, ["pass"])
    orchestrator = Orchestrator(
        project_dir=tmp_path,
        model_config=ModelConfig("m", "m", "m"),
        max_rounds=1,
        phase_runner=runner,
        client_factory=dummy_client_factory,
    )
    import pytest

    with pytest.raises(ValueError, match="Cannot use --planner-only and --qa-only together"):
        asyncio.run(orchestrator.run(resume=False, planner_only=True, qa_only=True))


def test_model_overrides_use_compatibility_mode_without_shared_client(tmp_path: Path) -> None:
    runner = FakeRunner(tmp_path, ["pass"])
    orchestrator = Orchestrator(
        project_dir=tmp_path,
        model_config=ModelConfig("planner", "builder", "evaluator"),
        max_rounds=1,
        phase_runner=runner,
        client_factory=dummy_client_factory,
    )
    asyncio.run(orchestrator.run(resume=False))
    assert runner.clients_by_phase["planner"][0] is None
    assert runner.clients_by_phase["builder"][0] is None
    assert runner.clients_by_phase["evaluator"][0] is None
