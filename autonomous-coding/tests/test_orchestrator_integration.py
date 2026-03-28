from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

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
        self.clients_by_phase: dict[str, list[object | None]] = {
            "planner": [],
            "builder": [],
            "evaluator": [],
            "contract_reviewer": [],
        }

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
        if phase == "contract_reviewer":
            return json.dumps(
                {
                    "status": "changes_requested",
                    "confidence_score": 0.61,
                    "reason_codes": ["OUT_OF_SCOPE"],
                    "actionable_suggestions": ["Reduce scope to one user-visible workflow."],
                    "rationale": "Proposal exceeds current round scope.",
                }
            )
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
    usage = state.llm_usage
    assert usage["calls_total"] >= 3
    assert usage["by_phase"]["planner"]["calls"] == 1


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
    assert state["status"] == "building"


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


def test_shared_session_can_be_disabled_even_with_identical_models(tmp_path: Path) -> None:
    runner = FakeRunner(tmp_path, ["pass"])
    orchestrator = Orchestrator(
        project_dir=tmp_path,
        model_config=ModelConfig("m", "m", "m"),
        max_rounds=1,
        phase_runner=runner,
        client_factory=dummy_client_factory,
        shared_session_enabled=False,
    )
    asyncio.run(orchestrator.run(resume=False))
    assert runner.clients_by_phase["planner"][0] is None
    assert runner.clients_by_phase["builder"][0] is None
    assert runner.clients_by_phase["evaluator"][0] is None


def test_round_two_contract_uses_previous_builder_proposal(tmp_path: Path) -> None:
    class ProposalRunner(FakeRunner):
        async def __call__(self, project_dir: Path, model: str, prompt: str, phase: str, client=None) -> str:
            result = await super().__call__(project_dir, model, prompt, phase, client)
            if phase == "builder" and self.builder_calls == 1:
                proposal = project_dir / "planning" / "sprint_proposal_round_01.md"
                proposal.write_text(
                    "# Sprint Proposal Round 01\n\n"
                    "## Proposed features in scope\n"
                    "- Ship profile settings page\n\n"
                    "## Proposed acceptance tests\n"
                    "- AC-NEXT-1 | Settings save persists after refresh | Open /settings and refresh\n"
                )
            return result

    runner = ProposalRunner(tmp_path, ["fail", "pass"])
    orchestrator = Orchestrator(
        project_dir=tmp_path,
        model_config=ModelConfig("m", "m", "m"),
        max_rounds=2,
        phase_runner=runner,
        client_factory=dummy_client_factory,
    )
    asyncio.run(orchestrator.run(resume=False))

    contract_round_02 = json.loads((tmp_path / "planning" / "sprint_contract_round_02.json").read_text())
    assert "Ship profile settings page" in contract_round_02["features_in_scope"]
    counts: dict[str, int] = {}
    for feature in contract_round_02["features_in_scope"]:
        counts[feature] = counts.get(feature, 0) + 1
    duplicates = {feature for feature, count in counts.items() if count > 1}
    assert not duplicates, f"Duplicate features in round 2 contract: {duplicates}"
    assert any(test["id"] == "AC-NEXT-1" for test in contract_round_02["acceptance_tests"])


def test_round_two_contract_dedups_proposed_acceptance_ids(tmp_path: Path) -> None:
    class ProposalRunner(FakeRunner):
        async def __call__(self, project_dir: Path, model: str, prompt: str, phase: str, client=None) -> str:
            result = await super().__call__(project_dir, model, prompt, phase, client)
            if phase == "builder" and self.builder_calls == 1:
                proposal = project_dir / "planning" / "sprint_proposal_round_01.md"
                proposal.write_text(
                    "# Sprint Proposal Round 01\n\n"
                    "## Proposed features in scope\n"
                    "- Feature A\n\n"
                    "## Proposed acceptance tests\n"
                    "- AC-1 | Duplicate of prior criterion | Browser QA path A\n"
                    "- AC-NEW | New criterion | Browser QA path B\n"
                    "- AC-NEW | Duplicate proposal id | Browser QA path C\n"
                )
            return result

    runner = ProposalRunner(tmp_path, ["fail", "pass"])
    orchestrator = Orchestrator(
        project_dir=tmp_path,
        model_config=ModelConfig("m", "m", "m"),
        max_rounds=2,
        phase_runner=runner,
        client_factory=dummy_client_factory,
    )
    asyncio.run(orchestrator.run(resume=False))

    contract_round_02 = json.loads((tmp_path / "planning" / "sprint_contract_round_02.json").read_text())
    ids = [item["id"] for item in contract_round_02["acceptance_tests"]]
    assert "AC-1" not in ids
    assert ids.count("AC-NEW") == 1


def test_run_state_persists_llm_usage_metrics(tmp_path: Path) -> None:
    runner = FakeRunner(tmp_path, ["pass"])
    orchestrator = Orchestrator(
        project_dir=tmp_path,
        model_config=ModelConfig("m", "m", "m"),
        max_rounds=1,
        phase_runner=runner,
        client_factory=dummy_client_factory,
    )
    state = asyncio.run(orchestrator.run(resume=False))
    usage = state.llm_usage
    assert usage["calls_total"] == 3
    assert usage["totals"]["total_tokens"] > 0
    assert usage["totals"]["estimated_cost_usd"] > 0
    assert usage["by_phase"]["planner"]["calls"] == 1
    assert usage["by_phase"]["builder"]["calls"] == 1
    assert usage["by_phase"]["evaluator"]["calls"] == 1


def test_malformed_proposal_creates_changes_requested_negotiation(tmp_path: Path) -> None:
    class MalformedProposalRunner(FakeRunner):
        async def __call__(self, project_dir: Path, model: str, prompt: str, phase: str, client=None) -> str:
            result = await super().__call__(project_dir, model, prompt, phase, client)
            if phase == "builder" and self.builder_calls == 1:
                proposal = project_dir / "planning" / "sprint_proposal_round_01.md"
                proposal.write_text(
                    "# Sprint Proposal Round 01\n\n"
                    "## Proposed acceptance tests\n"
                    "- missing separators line\n"
                )
            return result

    runner = MalformedProposalRunner(tmp_path, ["fail", "pass"])
    orchestrator = Orchestrator(
        project_dir=tmp_path,
        model_config=ModelConfig("m", "m", "m"),
        max_rounds=2,
        phase_runner=runner,
        client_factory=dummy_client_factory,
    )
    asyncio.run(orchestrator.run(resume=False))

    negotiation = json.loads((tmp_path / "planning" / "sprint_contract_negotiation_round_02.json").read_text())
    assert negotiation["status"] == "changes_requested"
    assert negotiation["feedback"]
    assert "FORMAT_ERROR" in negotiation["reason_codes"]
    assert negotiation["review_mode"] == "deterministic"


def test_llm_contract_review_enriches_negotiation_artifact(tmp_path: Path) -> None:
    runner = FakeRunner(tmp_path, ["fail", "pass"])
    orchestrator = Orchestrator(
        project_dir=tmp_path,
        model_config=ModelConfig("m", "m", "m"),
        max_rounds=2,
        phase_runner=runner,
        client_factory=dummy_client_factory,
        llm_contract_review=True,
    )
    asyncio.run(orchestrator.run(resume=False))

    negotiation = json.loads((tmp_path / "planning" / "sprint_contract_negotiation_round_02.json").read_text())
    assert negotiation["review_mode"] == "llm_assisted"
    assert negotiation["turns_used"] == 2
    assert negotiation["status"] == "changes_requested"
    assert "LLM_ARBITRATION_REQUESTED" in negotiation["reason_codes"]
    assert "OUT_OF_SCOPE" in negotiation["reason_codes"]
    assert negotiation["confidence_score"] == pytest.approx(0.61)
