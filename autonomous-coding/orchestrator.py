"""V2 autonomous coding orchestrator (planner -> builder -> evaluator)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from artifacts import ArtifactPaths, read_json, write_validated_json
from builder import BuilderPhase
from evaluator import EvaluatorPhase
from planner import PlannerPhase
from state_models import RoundState, RunState, RunStatus


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
        phase_runner: Callable,
    ):
        self.project_dir = project_dir
        self.paths = ArtifactPaths(project_dir)
        self.paths.ensure_dirs()
        self.model_config = model_config
        self.max_rounds = max_rounds
        self.planner = PlannerPhase(phase_runner)
        self.builder = BuilderPhase(phase_runner)
        self.evaluator = EvaluatorPhase(phase_runner)

    def _load_run_state(self) -> RunState:
        payload = read_json(self.paths.run_state)
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

    async def run(self, resume: bool = True, planner_only: bool = False, qa_only: bool = False) -> RunState:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        run_state = self._load_run_state() if resume else RunState(max_rounds=self.max_rounds)

        if planner_only and qa_only:
            raise ValueError("Cannot use --planner-only and --qa-only together")

        if not qa_only and not run_state.planner_complete:
            print("[V2] Running planner phase")
            run_state.status = RunStatus.PLANNING
            self._save_run_state(run_state)
            planner_result = await self.planner.run(self.project_dir, self.model_config.planner_model)
            run_state.planner_complete = True
            run_state.latest_summary = planner_result.summary[:4000]
            self._save_run_state(run_state)

        if planner_only:
            run_state.status = RunStatus.NOT_STARTED
            self._save_run_state(run_state)
            return run_state

        next_round = max(1, run_state.current_round + 1)

        if qa_only:
            print(f"[V2] Running evaluator-only mode for round {next_round}")
            run_state.status = RunStatus.EVALUATING
            self._save_run_state(run_state)
            eval_result = await self.evaluator.run(self.project_dir, self.model_config.evaluator_model, next_round)
            run_state.current_round = next_round
            run_state.status = RunStatus.COMPLETED if eval_result.result == "pass" else RunStatus.BLOCKED
            run_state.completed = eval_result.result == "pass"
            run_state.latest_summary = eval_result.summary[:4000]
            self._save_round_state(
                RoundState(
                    round_number=next_round,
                    evaluator_report_json_path=str(eval_result.report_json_path),
                    evaluator_report_md_path=str(eval_result.report_md_path),
                    outcome=eval_result.result,
                    blocking_issues=eval_result.blocking_issues,
                )
            )
            self._save_run_state(run_state)
            return run_state

        for round_number in range(next_round, self.max_rounds + 1):
            print(f"[V2] Round {round_number}/{self.max_rounds}: builder")
            run_state.status = RunStatus.BUILDING
            run_state.current_round = round_number
            self._save_run_state(run_state)
            build_result = await self.builder.run(self.project_dir, self.model_config.builder_model, round_number)

            print(f"[V2] Round {round_number}/{self.max_rounds}: evaluator")
            run_state.status = RunStatus.EVALUATING
            run_state.latest_summary = build_result.summary[:4000]
            self._save_run_state(run_state)
            eval_result = await self.evaluator.run(self.project_dir, self.model_config.evaluator_model, round_number)

            round_state = RoundState(
                round_number=round_number,
                builder_report_path=str(build_result.report_path),
                evaluator_report_json_path=str(eval_result.report_json_path),
                evaluator_report_md_path=str(eval_result.report_md_path),
                outcome=eval_result.result,
                blocking_issues=eval_result.blocking_issues,
            )
            self._save_round_state(round_state)

            if eval_result.result == "pass":
                run_state.status = RunStatus.COMPLETED
                run_state.completed = True
                run_state.latest_summary = eval_result.summary[:4000]
                self._save_run_state(run_state)
                print(f"[V2] Completed successfully in round {round_number}")
                return run_state

            run_state.status = RunStatus.BLOCKED
            run_state.completed = False
            run_state.latest_summary = eval_result.summary[:4000]
            self._save_run_state(run_state)
            print(f"[V2] Evaluator reported {eval_result.result}; continuing if rounds remain")

        print("[V2] Max rounds reached without pass")
        return run_state
