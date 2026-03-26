"""V3.2 autonomous coding orchestrator (planner -> builder -> evaluator)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from artifacts import ArtifactPaths, read_json, write_validated_json
from builder import BuilderPhase
from client import create_client
from evaluator import EvaluatorPhase
from phase_types import ClientFactory, PhaseRunner
from planner import PlannerPhase
from state_models import RoundState, RunState, RunStatus

SUMMARY_MAX_CHARS = int(os.environ.get("V3_1_SUMMARY_MAX_CHARS", "8000"))
MAX_SCOPE_ITEMS = int(os.environ.get("V3_2_SPRINT_MAX_SCOPE_ITEMS", "10"))
MAX_ACCEPTANCE_TESTS = int(os.environ.get("V3_2_SPRINT_MAX_ACCEPTANCE_TESTS", "12"))


@dataclass
class ModelConfig:
    planner_model: str
    builder_model: str
    evaluator_model: str


class Orchestrator:
    """Coordinates planning, build, and QA rounds with resume-safe state."""

    def __init__(
        self,
        project_dir: Path,
        model_config: ModelConfig,
        max_rounds: int,
        phase_runner: PhaseRunner,
        client_factory: ClientFactory = create_client,
    ):
        self.project_dir = project_dir
        self.paths = ArtifactPaths(project_dir)
        self.paths.ensure_dirs()
        self.model_config = model_config
        self.max_rounds = max_rounds
        self.phase_runner = phase_runner
        self.client_factory = client_factory
        self.planner = PlannerPhase(phase_runner)
        self.builder = BuilderPhase(phase_runner)
        self.evaluator = EvaluatorPhase(phase_runner)
        self.phase_timings: dict[str, list[float]] = {"planner": [], "builder": [], "evaluator": []}

    def _load_run_state(self) -> RunState:
        payload = read_json(self.paths.run_state, context="run_state")
        if not payload:
            return RunState(max_rounds=self.max_rounds)
        state = RunState.from_dict(payload)
        state.max_rounds = self.max_rounds
        return state

    def _save_run_state(self, state: RunState) -> None:
        state.touch()
        write_validated_json(self.paths.run_state, state.to_dict(), "run_state")

    def _save_round_state(self, round_state: RoundState) -> None:
        write_validated_json(
            self.paths.round_state(round_state.round_number),
            round_state.to_dict(),
            "round_state",
        )

    def _summarize(self, text: str) -> str:
        return text[:SUMMARY_MAX_CHARS]

    def _continuous_session_enabled(self) -> bool:
        models = {
            self.model_config.planner_model,
            self.model_config.builder_model,
            self.model_config.evaluator_model,
        }
        return len(models) == 1

    def _get_attempted_features(self, round_number: int) -> set[str]:
        attempted: set[str] = set()
        for prev_round in range(1, round_number):
            prev_contract = self.paths.sprint_contract_json(prev_round)
            payload = read_json(prev_contract, context=f"sprint_contract_round_{prev_round:02d}")
            if not isinstance(payload, dict):
                continue
            for feature in payload.get("features_in_scope", []):
                if isinstance(feature, str) and feature.strip():
                    attempted.add(feature.strip())
        return attempted

    def _get_previously_assigned_criteria_ids(self, round_number: int) -> set[str]:
        assigned: set[str] = set()
        for prev_round in range(1, round_number):
            prev_contract = self.paths.sprint_contract_json(prev_round)
            payload = read_json(prev_contract, context=f"sprint_contract_round_{prev_round:02d}")
            if not isinstance(payload, dict):
                continue
            for test in payload.get("acceptance_tests", []):
                if isinstance(test, dict):
                    test_id = test.get("id")
                    if isinstance(test_id, str) and test_id.strip():
                        assigned.add(test_id.strip())
        return assigned

    def _load_previous_sprint_proposal(self, round_number: int) -> tuple[list[str], list[dict[str, str]]]:
        if round_number <= 1:
            return [], []

        proposal_path = self.paths.planning_dir / f"sprint_proposal_round_{round_number - 1:02d}.md"
        if not proposal_path.exists():
            return [], []

        proposed_features: list[str] = []
        proposed_acceptance: list[dict[str, str]] = []
        section = ""
        for raw_line in proposal_path.read_text().splitlines():
            line = raw_line.strip()
            if line.lower().startswith("## proposed features in scope"):
                section = "features"
                continue
            if line.lower().startswith("## proposed acceptance tests"):
                section = "tests"
                continue
            if not line.startswith("- "):
                continue

            body = line[2:].strip()
            if section == "features" and body:
                proposed_features.append(body)
            elif section == "tests" and body:
                chunks = [chunk.strip() for chunk in body.split("|")]
                if len(chunks) >= 3:
                    proposed_acceptance.append(
                        {
                            "id": chunks[0] or "AC-PROPOSAL",
                            "criterion": chunks[1] or "Criterion from builder proposal",
                            "verification_method": chunks[2] or "Browser QA with reproducible steps",
                        }
                    )

        return proposed_features, proposed_acceptance

    def _build_sprint_contract(self, round_number: int) -> Path:
        acceptance = read_json(self.paths.acceptance_criteria, context="acceptance_criteria")
        backlog = read_json(self.paths.work_backlog, context="work_backlog")
        attempted_features = self._get_attempted_features(round_number)
        previous_criteria_ids = self._get_previously_assigned_criteria_ids(round_number)
        proposed_features, proposed_acceptance = self._load_previous_sprint_proposal(round_number)

        backlog_items = backlog.get("items", []) if isinstance(backlog, dict) else []
        in_scope = [
            item.get("title", "Unnamed backlog item")
            for item in backlog_items
            if item.get("status") != "done" and item.get("title", "").strip() not in attempted_features
        ]
        if proposed_features:
            in_scope = proposed_features + in_scope

        deduped_in_scope = list(dict.fromkeys([feature.strip() for feature in in_scope if feature and feature.strip()]))
        in_scope = deduped_in_scope[:MAX_SCOPE_ITEMS] or ["Address QA blockers from previous round"]

        criteria = acceptance.get("criteria", []) if isinstance(acceptance, dict) else []
        if not criteria:
            print(
                f"[V3.2] WARNING: acceptance_criteria.json is empty or missing for round {round_number}. "
                "Sprint contract uses generic fallback. Consider re-running planner phase."
            )

        acceptance_tests = [
            {
                "id": criterion.get("id", f"AC-{idx+1:03d}"),
                "criterion": criterion.get("description", "Criterion description missing"),
                "verification_method": "Browser QA with screenshots and reproducible steps",
            }
            for idx, criterion in enumerate(criteria)
            if criterion.get("id", f"AC-{idx+1:03d}") not in previous_criteria_ids
        ]
        if proposed_acceptance:
            acceptance_tests = proposed_acceptance + acceptance_tests

        acceptance_tests = acceptance_tests[:MAX_ACCEPTANCE_TESTS]
        if not acceptance_tests:
            acceptance_tests = [
                {
                    "id": "AC-FALLBACK-001",
                    "criterion": "Core app route loads and one main user workflow succeeds",
                    "verification_method": "Open app via browser tooling and complete workflow",
                }
            ]

        payload = {
            "round_number": round_number,
            "features_in_scope": in_scope,
            "acceptance_tests": acceptance_tests,
        }
        contract_path = self.paths.sprint_contract_json(round_number)
        write_validated_json(contract_path, payload, "sprint_contract")
        return contract_path

    def _print_metrics(self) -> None:
        print("\n[V3.2] Phase timing summary:")
        for phase, durations in self.phase_timings.items():
            if not durations:
                continue
            total = sum(durations)
            print(f"  {phase}: count={len(durations)} total={total:.2f}s avg={total/len(durations):.2f}s")
        print("[V3.2] Token/cost metrics: not available from current runner interface.")

    async def run(self, resume: bool = True, planner_only: bool = False, qa_only: bool = False) -> RunState:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        run_state = self._load_run_state() if resume else RunState(max_rounds=self.max_rounds)

        if planner_only and qa_only:
            raise ValueError("Cannot use --planner-only and --qa-only together")

        if resume and run_state.completed:
            print(
                f"[V3.2] Run already completed on status={run_state.status.value}. "
                "Use --resume=False or remove state/run_state.json to restart."
            )
            return run_state

        continuous_session = self._continuous_session_enabled()
        shared_client: Any = None
        if continuous_session:
            model = self.model_config.builder_model
            print(f"[V3.2] Continuous session mode enabled with model={model}")
            shared_client = self.client_factory(self.project_dir, model, "evaluator")
        else:
            print(
                "[V3.2] Compatibility mode enabled: per-phase model overrides require phase-scoped sessions; "
                "continuous shared context disabled."
            )

        async def _run_loop(client: Any = None) -> RunState:
            nonlocal run_state
            if not qa_only and not run_state.planner_complete:
                print("[V3.2] Running planner phase")
                run_state.status = RunStatus.PLANNING
                self._save_run_state(run_state)
                t0 = time.monotonic()
                planner_result = await self.planner.run(
                    self.project_dir, self.model_config.planner_model, client=client
                )
                self.phase_timings["planner"].append(time.monotonic() - t0)
                run_state.planner_complete = True
                run_state.latest_summary = self._summarize(planner_result.summary)
                self._save_run_state(run_state)

            if planner_only:
                run_state.status = RunStatus.NOT_STARTED
                self._save_run_state(run_state)
                return run_state

            next_round = max(1, run_state.current_round + 1)

            if qa_only:
                print(f"[V3.2] Running evaluator-only mode for round {next_round}")
                sprint_contract_path = self._build_sprint_contract(next_round)
                run_state.status = RunStatus.EVALUATING
                self._save_run_state(run_state)
                t0 = time.monotonic()
                eval_result = await self.evaluator.run(
                    self.project_dir,
                    self.model_config.evaluator_model,
                    next_round,
                    sprint_contract_path,
                    client=client,
                )
                self.phase_timings["evaluator"].append(time.monotonic() - t0)
                run_state.current_round = next_round
                run_state.status = RunStatus.COMPLETED if eval_result.result == "pass" else RunStatus.BLOCKED
                run_state.completed = eval_result.result == "pass"
                run_state.latest_summary = self._summarize(eval_result.summary)
                self._save_round_state(
                    RoundState(
                        round_number=next_round,
                        sprint_contract_json_path=str(sprint_contract_path),
                        evaluator_report_json_path=str(eval_result.report_json_path),
                        evaluator_report_md_path=str(eval_result.report_md_path),
                        outcome=eval_result.result,
                        blocking_issues=eval_result.blocking_issues,
                    )
                )
                self._save_run_state(run_state)
                return run_state

            for round_number in range(next_round, self.max_rounds + 1):
                sprint_contract_path = self._build_sprint_contract(round_number)

                print(f"[V3.2] Round {round_number}/{self.max_rounds}: builder")
                run_state.status = RunStatus.BUILDING
                self._save_run_state(run_state)
                t0 = time.monotonic()
                build_result = await self.builder.run(
                    self.project_dir,
                    self.model_config.builder_model,
                    round_number,
                    sprint_contract_path,
                    client=client,
                )
                self.phase_timings["builder"].append(time.monotonic() - t0)

                print(f"[V3.2] Round {round_number}/{self.max_rounds}: evaluator")
                run_state.status = RunStatus.EVALUATING
                run_state.latest_summary = self._summarize(build_result.summary)
                self._save_run_state(run_state)
                t0 = time.monotonic()
                eval_result = await self.evaluator.run(
                    self.project_dir,
                    self.model_config.evaluator_model,
                    round_number,
                    sprint_contract_path,
                    client=client,
                )
                self.phase_timings["evaluator"].append(time.monotonic() - t0)

                round_state = RoundState(
                    round_number=round_number,
                    sprint_contract_json_path=str(sprint_contract_path),
                    builder_report_path=str(build_result.report_path),
                    evaluator_report_json_path=str(eval_result.report_json_path),
                    evaluator_report_md_path=str(eval_result.report_md_path),
                    outcome=eval_result.result,
                    blocking_issues=eval_result.blocking_issues,
                )
                self._save_round_state(round_state)

                run_state.current_round = round_number
                if eval_result.result == "pass":
                    run_state.status = RunStatus.COMPLETED
                    run_state.completed = True
                    run_state.latest_summary = self._summarize(eval_result.summary)
                    self._save_run_state(run_state)
                    print(f"[V3.2] Completed successfully in round {round_number}")
                    return run_state

                run_state.status = RunStatus.BLOCKED
                run_state.completed = False
                run_state.latest_summary = self._summarize(eval_result.summary)
                self._save_run_state(run_state)
                print(f"[V3.2] Evaluator reported {eval_result.result}; continuing if rounds remain")

            print("[V3.2] Max rounds reached without pass")
            return run_state

        if shared_client is None:
            final_state = await _run_loop(client=None)
            self._print_metrics()
            return final_state

        async with shared_client:
            final_state = await _run_loop(client=shared_client)

        self._print_metrics()
        return final_state
