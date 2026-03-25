from __future__ import annotations

import json
from pathlib import Path

from orchestrator import ModelConfig, Orchestrator


class FakeRunner:
    def __init__(self, project_dir: Path, outcomes: list[str]):
        self.project_dir = project_dir
        self.outcomes = outcomes
        self.eval_calls = 0

    async def __call__(self, project_dir: Path, model: str, prompt: str, phase: str) -> str:
        del model, prompt
        if phase == "planner":
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
        return f"fake {phase}"


def test_first_run_then_complete(tmp_path: Path) -> None:
    runner = FakeRunner(tmp_path, ["pass"])
    orchestrator = Orchestrator(
        project_dir=tmp_path,
        model_config=ModelConfig("p", "b", "e"),
        max_rounds=2,
        phase_runner=runner,
    )
    state = __import__("asyncio").run(orchestrator.run(resume=False))
    assert state.completed is True
    assert state.current_round == 1


def test_retry_loop_then_pass(tmp_path: Path) -> None:
    runner = FakeRunner(tmp_path, ["fail", "pass"])
    orchestrator = Orchestrator(
        project_dir=tmp_path,
        model_config=ModelConfig("p", "b", "e"),
        max_rounds=3,
        phase_runner=runner,
    )
    state = __import__("asyncio").run(orchestrator.run(resume=False))
    assert state.completed is True
    assert state.current_round == 2


def test_resume_skips_planner(tmp_path: Path) -> None:
    runner = FakeRunner(tmp_path, ["fail", "pass"])
    orchestrator = Orchestrator(
        project_dir=tmp_path,
        model_config=ModelConfig("p", "b", "e"),
        max_rounds=3,
        phase_runner=runner,
    )
    __import__("asyncio").run(orchestrator.run(resume=False))

    runner2 = FakeRunner(tmp_path, ["pass"])
    orchestrator2 = Orchestrator(
        project_dir=tmp_path,
        model_config=ModelConfig("p", "b", "e"),
        max_rounds=4,
        phase_runner=runner2,
    )
    state = __import__("asyncio").run(orchestrator2.run(resume=True, qa_only=True))
    assert state.current_round >= 1
