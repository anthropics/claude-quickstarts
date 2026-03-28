"""V3.6.3 autonomous coding orchestrator (planner -> builder -> evaluator)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from artifacts import ArtifactPaths, read_json, write_validated_json
from builder import BuilderPhase
from client import create_client
from evaluator import EvaluatorPhase
from metrics import default_run_usage
from phase_types import ClientFactory, PhaseRunner
from planner import PlannerPhase
from state_models import RoundState, RunState, RunStatus

SUMMARY_MAX_CHARS = int(os.environ.get("V3_1_SUMMARY_MAX_CHARS", "8000"))
MAX_SCOPE_ITEMS = int(os.environ.get("V3_4_SPRINT_MAX_SCOPE_ITEMS", os.environ.get("V3_2_SPRINT_MAX_SCOPE_ITEMS", "10")))
MAX_ACCEPTANCE_TESTS = int(
    os.environ.get("V3_4_SPRINT_MAX_ACCEPTANCE_TESTS", os.environ.get("V3_2_SPRINT_MAX_ACCEPTANCE_TESTS", "12"))
)
MAX_NEGOTIATION_TURNS = int(os.environ.get("V3_4_MAX_NEGOTIATION_TURNS", "2"))
LOG_VERSION_TAG = "V3.6.3"

NEGOTIATION_REASON_CODES = {
    "FORMAT_ERROR",
    "DUPLICATE_AC",
    "OUT_OF_SCOPE",
    "EMPTY_PROPOSAL",
    "PROPOSAL_MISSING",
    "LLM_ARBITRATION_REQUESTED",
    "LLM_RESPONSE_INVALID",
}


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
        llm_contract_review: bool = False,
        target_test_count: int = 200,
    ):
        self.project_dir = project_dir
        self.paths = ArtifactPaths(project_dir)
        self.paths.ensure_dirs()
        self.model_config = model_config
        self.max_rounds = max_rounds
        self.phase_runner = phase_runner
        self.client_factory = client_factory
        self.llm_contract_review = llm_contract_review
        self.planner = PlannerPhase(phase_runner, target_test_count=target_test_count)
        self.builder = BuilderPhase(phase_runner)
        self.evaluator = EvaluatorPhase(phase_runner)
        self.phase_timings: dict[str, list[float]] = {"planner": [], "builder": [], "evaluator": []}

    def _record_usage(self, state: RunState, phase: str, usage: dict[str, Any]) -> None:
        usage_root = state.llm_usage or default_run_usage()
        by_phase = usage_root.get("by_phase", {})
        phase_bucket = by_phase.get(phase, {})
        totals = usage_root.get("totals", {})
        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
        total_tokens = int(usage.get("total_tokens", input_tokens + output_tokens))
        estimated_cost = float(usage.get("estimated_cost_usd", 0.0))

        phase_bucket["calls"] = int(phase_bucket.get("calls", 0)) + 1
        phase_bucket["input_tokens"] = int(phase_bucket.get("input_tokens", 0)) + input_tokens
        phase_bucket["output_tokens"] = int(phase_bucket.get("output_tokens", 0)) + output_tokens
        phase_bucket["total_tokens"] = int(phase_bucket.get("total_tokens", 0)) + total_tokens
        phase_bucket["estimated_cost_usd"] = float(phase_bucket.get("estimated_cost_usd", 0.0)) + estimated_cost
        by_phase[phase] = phase_bucket

        usage_root["calls_total"] = int(usage_root.get("calls_total", 0)) + 1
        totals["input_tokens"] = int(totals.get("input_tokens", 0)) + input_tokens
        totals["output_tokens"] = int(totals.get("output_tokens", 0)) + output_tokens
        totals["total_tokens"] = int(totals.get("total_tokens", 0)) + total_tokens
        totals["estimated_cost_usd"] = float(totals.get("estimated_cost_usd", 0.0)) + estimated_cost
        usage_root["totals"] = totals
        usage_root["by_phase"] = by_phase
        state.llm_usage = usage_root

        print(
            f"[{LOG_VERSION_TAG}] Phase-end {phase} usage: "
            f"calls={phase_bucket['calls']} total_tokens={phase_bucket['total_tokens']} "
            f"est_cost=${phase_bucket['estimated_cost_usd']:.6f} (cumulative phase)"
        )

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
            if not prev_contract.exists():
                print(
                    f"[{LOG_VERSION_TAG}] INFO: sprint_contract_round_{prev_round:02d}.json not found; "
                    f"criteria deduplication for round {round_number} may be incomplete."
                )
                continue
            payload = read_json(prev_contract, context=f"sprint_contract_round_{prev_round:02d}")
            if not isinstance(payload, dict):
                continue
            for test in payload.get("acceptance_tests", []):
                if isinstance(test, dict):
                    test_id = test.get("id")
                    if isinstance(test_id, str) and test_id.strip():
                        assigned.add(test_id.strip())
        return assigned

    def _normalize_acceptance_id(self, value: str, idx: int, round_number: int) -> str:
        normalized = "-".join(value.strip().split())
        if normalized:
            return normalized
        return f"AC-PROPOSAL-R{round_number:02d}-{idx:03d}"

    def _load_previous_sprint_proposal(
        self, round_number: int
    ) -> tuple[list[str], list[dict[str, str]], list[str]]:
        if round_number <= 1:
            return [], [], []

        proposal_path = self.paths.sprint_proposal_md(round_number - 1)
        if not proposal_path.exists():
            print(
                f"[{LOG_VERSION_TAG}] INFO: No sprint proposal found for round {round_number - 1} "
                f"(expected at {proposal_path}). Contract built from backlog only."
            )
            return [], [], [f"proposal_missing_round_{round_number - 1:02d}"]

        proposed_features: list[str] = []
        proposed_acceptance: list[dict[str, str]] = []
        parse_issues: list[str] = []
        section = ""
        for line_number, raw_line in enumerate(proposal_path.read_text().splitlines(), start=1):
            line = raw_line.strip()
            if line.startswith("##"):
                if "proposed features in scope" in line.lower():
                    section = "features"
                elif "proposed acceptance tests" in line.lower():
                    section = "tests"
                else:
                    section = ""
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
                            "id": self._normalize_acceptance_id(chunks[0], len(proposed_acceptance) + 1, round_number),
                            "criterion": chunks[1] or "Criterion from builder proposal",
                            "verification_method": chunks[2] or "Browser QA with reproducible steps",
                        }
                    )
                else:
                    parse_issues.append(
                        f"line_{line_number}: invalid acceptance test format; expected "
                        "'- ID | Criterion | Verification method'"
                    )
            elif body:
                parse_issues.append(
                    f"line_{line_number}: bullet under unknown section ignored"
                )

        return proposed_features, proposed_acceptance, parse_issues

    def _derive_reason_codes(
        self,
        parse_issues: list[str],
        proposed_features: list[str],
        proposed_acceptance: list[dict[str, str]],
    ) -> list[str]:
        codes: list[str] = []

        if not proposed_features and not proposed_acceptance:
            codes.append("EMPTY_PROPOSAL")

        if any(issue.startswith("proposal_missing_round_") for issue in parse_issues):
            codes.append("PROPOSAL_MISSING")

        if any("invalid acceptance test format" in issue or "unknown section" in issue for issue in parse_issues):
            codes.append("FORMAT_ERROR")

        seen: set[str] = set()
        duplicate_found = False
        for test in proposed_acceptance:
            test_id = str(test.get("id", "")).strip()
            if not test_id:
                continue
            if test_id in seen:
                duplicate_found = True
                break
            seen.add(test_id)
        if duplicate_found:
            codes.append("DUPLICATE_AC")

        return list(dict.fromkeys(codes))

    def _build_contract_review_prompt(
        self,
        round_number: int,
        proposed_features: list[str],
        proposed_acceptance: list[dict[str, str]],
        parse_issues: list[str],
        deterministic_status: str,
        deterministic_feedback: list[str],
        deterministic_reason_codes: list[str],
    ) -> str:
        allowed_codes = ", ".join(sorted(NEGOTIATION_REASON_CODES))
        proposal_payload = {
            "round_number": round_number,
            "proposed_features": proposed_features,
            "proposed_acceptance_tests": proposed_acceptance,
            "parse_issues": parse_issues,
            "deterministic_review": {
                "status": deterministic_status,
                "feedback": deterministic_feedback,
                "reason_codes": deterministic_reason_codes,
            },
        }
        return (
            "You are an evaluator contract reviewer for sprint-contract negotiation.\n"
            "Return STRICT JSON only (no markdown).\n"
            "Required keys: status, confidence_score, reason_codes, actionable_suggestions, rationale.\n"
            'status must be "approved" or "changes_requested".\n'
            "confidence_score must be a float from 0.0 to 1.0.\n"
            f"reason_codes must be an array of values from: {allowed_codes}.\n"
            "actionable_suggestions must be short, concrete bullets for builder/planner.\n"
            "rationale must be brief and deterministic.\n\n"
            "Input payload:\n"
            f"{json.dumps(proposal_payload, indent=2)}"
        )

    async def _llm_review_proposal(
        self,
        round_number: int,
        proposed_features: list[str],
        proposed_acceptance: list[dict[str, str]],
        parse_issues: list[str],
        deterministic_status: str,
        deterministic_feedback: list[str],
        deterministic_reason_codes: list[str],
        client: Any = None,
    ) -> dict[str, Any]:
        prompt = self._build_contract_review_prompt(
            round_number,
            proposed_features,
            proposed_acceptance,
            parse_issues,
            deterministic_status,
            deterministic_feedback,
            deterministic_reason_codes,
        )
        response = await self.phase_runner(
            self.project_dir,
            self.model_config.evaluator_model,
            prompt,
            "contract_reviewer",
            client,
        )
        try:
            payload = json.loads(response)
        except json.JSONDecodeError:
            return {
                "status": deterministic_status,
                "confidence_score": 0.0,
                "reason_codes": ["LLM_RESPONSE_INVALID"],
                "actionable_suggestions": [],
                "rationale": "LLM contract review returned invalid JSON; deterministic review retained.",
            }

        status = payload.get("status")
        if status not in {"approved", "changes_requested"}:
            status = deterministic_status

        confidence = payload.get("confidence_score", 0.0)
        try:
            confidence_score = float(confidence)
        except (TypeError, ValueError):
            confidence_score = 0.0
        confidence_score = max(0.0, min(1.0, confidence_score))

        raw_codes = payload.get("reason_codes", [])
        reason_codes = [
            code for code in raw_codes if isinstance(code, str) and code in NEGOTIATION_REASON_CODES
        ]
        reason_codes = list(dict.fromkeys(reason_codes))
        if not reason_codes:
            reason_codes = ["LLM_RESPONSE_INVALID"]

        raw_suggestions = payload.get("actionable_suggestions", [])
        suggestions = [item for item in raw_suggestions if isinstance(item, str) and item.strip()][:5]

        rationale = payload.get("rationale", "")
        if not isinstance(rationale, str):
            rationale = ""

        return {
            "status": status,
            "confidence_score": confidence_score,
            "reason_codes": reason_codes,
            "actionable_suggestions": suggestions,
            "rationale": rationale.strip(),
        }

    async def _review_proposal_and_write_negotiation(
        self,
        round_number: int,
        proposed_features: list[str],
        proposed_acceptance: list[dict[str, str]],
        parse_issues: list[str],
        client: Any = None,
    ) -> dict[str, Any]:
        feedback = list(parse_issues)
        status = "approved"
        if not proposed_features and not proposed_acceptance:
            status = "changes_requested"
            feedback.append("Proposal did not contain any actionable feature or acceptance test bullet.")
        if parse_issues:
            status = "changes_requested"
        reason_codes = self._derive_reason_codes(parse_issues, proposed_features, proposed_acceptance)
        confidence_score = 1.0 if status == "approved" else 0.35
        actionable_suggestions: list[str] = []
        review_mode = "deterministic"
        llm_rationale = ""
        turns_used = 1

        if self.llm_contract_review and round_number > 1:
            llm_review = await self._llm_review_proposal(
                round_number,
                proposed_features,
                proposed_acceptance,
                parse_issues,
                status,
                feedback,
                reason_codes,
                client,
            )
            review_mode = "llm_assisted"
            turns_used = min(MAX_NEGOTIATION_TURNS, 2)
            status = llm_review["status"]
            confidence_score = llm_review["confidence_score"]
            actionable_suggestions = llm_review["actionable_suggestions"]
            llm_rationale = llm_review["rationale"]
            reason_codes = list(dict.fromkeys(reason_codes + ["LLM_ARBITRATION_REQUESTED"] + llm_review["reason_codes"]))
            if llm_rationale:
                feedback.append(f"llm_arbitration: {llm_rationale}")
            if actionable_suggestions:
                feedback.extend([f"suggestion: {suggestion}" for suggestion in actionable_suggestions])

        review_payload = {
            "round_number": round_number,
            "status": status,
            "max_turns": MAX_NEGOTIATION_TURNS,
            "turns_used": turns_used,
            "feedback": feedback,
            "reason_codes": reason_codes,
            "confidence_score": confidence_score,
            "actionable_suggestions": actionable_suggestions,
            "review_mode": review_mode,
            "approved_features": proposed_features if status == "approved" else [],
            "approved_acceptance_tests": proposed_acceptance if status == "approved" else [],
        }
        write_validated_json(
            self.paths.sprint_contract_negotiation_json(round_number),
            review_payload,
            "sprint_contract_negotiation",
        )
        if feedback:
            print(f"[{LOG_VERSION_TAG}] INFO: round {round_number} proposal review feedback: {feedback}")
        return review_payload

    async def _build_sprint_contract(self, round_number: int, client: Any = None) -> Path:
        acceptance = read_json(self.paths.acceptance_criteria, context="acceptance_criteria")
        backlog = read_json(self.paths.work_backlog, context="work_backlog")
        attempted_features = self._get_attempted_features(round_number)
        previous_criteria_ids = self._get_previously_assigned_criteria_ids(round_number)
        proposed_features, proposed_acceptance, parse_issues = self._load_previous_sprint_proposal(round_number)
        negotiation = await self._review_proposal_and_write_negotiation(
            round_number,
            proposed_features,
            proposed_acceptance,
            parse_issues,
            client=client,
        )

        backlog_items = backlog.get("items", []) if isinstance(backlog, dict) else []
        if not backlog_items:
            print(
                f"[{LOG_VERSION_TAG}] WARNING: work_backlog.json is empty or missing for round {round_number}. "
                "Sprint scope uses generic fallback. Consider re-running planner phase."
            )
        in_scope = [
            item.get("title", "Unnamed backlog item")
            for item in backlog_items
            if item.get("status") != "done" and item.get("title", "").strip() not in attempted_features
        ]
        if negotiation["status"] == "approved" and proposed_features:
            new_proposals = [feature for feature in proposed_features if feature.strip() not in attempted_features]
            in_scope = new_proposals + in_scope

        deduped_in_scope = list(dict.fromkeys([feature.strip() for feature in in_scope if feature and feature.strip()]))
        in_scope = deduped_in_scope[:MAX_SCOPE_ITEMS] or ["Address QA blockers from previous round"]

        criteria = acceptance.get("criteria", []) if isinstance(acceptance, dict) else []
        if not criteria:
            print(
                f"[{LOG_VERSION_TAG}] WARNING: acceptance_criteria.json is empty or missing for round {round_number}. "
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
        deduped_acceptance: list[dict[str, str]] = []
        seen_ids: set[str] = set()
        for test in acceptance_tests:
            test_id = str(test.get("id", "")).strip()
            if not test_id or test_id in seen_ids:
                continue
            seen_ids.add(test_id)
            deduped_acceptance.append(test)

        if negotiation["status"] == "approved" and proposed_acceptance:
            for idx, proposed in enumerate(proposed_acceptance, start=1):
                proposed_id = self._normalize_acceptance_id(proposed.get("id", ""), idx, round_number)
                if proposed_id in previous_criteria_ids or proposed_id in seen_ids:
                    continue
                seen_ids.add(proposed_id)
                deduped_acceptance.insert(
                    0,
                    {
                        "id": proposed_id,
                        "criterion": proposed.get("criterion", "Criterion from builder proposal"),
                        "verification_method": proposed.get(
                            "verification_method", "Browser QA with screenshots and reproducible steps"
                        ),
                    },
                )

        acceptance_tests = deduped_acceptance

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
        print(f"\n[{LOG_VERSION_TAG}] Phase timing summary:")
        for phase, durations in self.phase_timings.items():
            if not durations:
                continue
            total = sum(durations)
            print(f"  {phase}: count={len(durations)} total={total:.2f}s avg={total/len(durations):.2f}s")
        print(f"[{LOG_VERSION_TAG}] Token/cost telemetry is tracked with best-effort estimation in state/run_state.json.")

    async def run(self, resume: bool = True, planner_only: bool = False, qa_only: bool = False) -> RunState:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        run_state = self._load_run_state() if resume else RunState(max_rounds=self.max_rounds)

        if planner_only and qa_only:
            raise ValueError("Cannot use --planner-only and --qa-only together")

        if resume and run_state.completed:
            print(
                f"[{LOG_VERSION_TAG}] Run already completed on status={run_state.status.value}. "
                "Use --resume=False or remove state/run_state.json to restart."
            )
            return run_state

        continuous_session = self._continuous_session_enabled()
        shared_client: Any = None
        if continuous_session:
            model = self.model_config.builder_model
            print(f"[{LOG_VERSION_TAG}] Continuous session mode enabled with model={model}")
            shared_client = self.client_factory(self.project_dir, model, "evaluator")
        else:
            print(
                f"[{LOG_VERSION_TAG}] Compatibility mode enabled: per-phase model overrides require phase-scoped sessions; "
                "continuous shared context disabled."
            )

        async def _run_loop(client: Any = None) -> RunState:
            nonlocal run_state
            if not qa_only and not run_state.planner_complete:
                print(f"[{LOG_VERSION_TAG}] Running planner phase")
                run_state.status = RunStatus.PLANNING
                self._save_run_state(run_state)
                t0 = time.monotonic()
                planner_result = await self.planner.run(
                    self.project_dir, self.model_config.planner_model, client=client
                )
                self.phase_timings["planner"].append(time.monotonic() - t0)
                self._record_usage(run_state, "planner", planner_result.usage.to_dict())
                run_state.planner_complete = True
                run_state.latest_summary = self._summarize(planner_result.summary)
                self._save_run_state(run_state)

            if planner_only:
                run_state.status = RunStatus.NOT_STARTED
                self._save_run_state(run_state)
                return run_state

            next_round = max(1, run_state.current_round + 1)

            if qa_only:
                print(f"[{LOG_VERSION_TAG}] Running evaluator-only mode for round {next_round}")
                sprint_contract_path = await self._build_sprint_contract(next_round, client=client)
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
                self._record_usage(run_state, "evaluator", eval_result.usage.to_dict())
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
                sprint_contract_path = await self._build_sprint_contract(round_number, client=client)

                print(f"[{LOG_VERSION_TAG}] Round {round_number}/{self.max_rounds}: builder")
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
                self._record_usage(run_state, "builder", build_result.usage.to_dict())

                print(f"[{LOG_VERSION_TAG}] Round {round_number}/{self.max_rounds}: evaluator")
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
                self._record_usage(run_state, "evaluator", eval_result.usage.to_dict())

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
                    print(f"[{LOG_VERSION_TAG}] Completed successfully in round {round_number}")
                    return run_state

                run_state.status = RunStatus.BLOCKED
                run_state.completed = False
                run_state.latest_summary = self._summarize(eval_result.summary)
                self._save_run_state(run_state)
                print(f"[{LOG_VERSION_TAG}] Evaluator reported {eval_result.result}; continuing if rounds remain")

            print(f"[{LOG_VERSION_TAG}] Max rounds reached without pass")
            return run_state

        if shared_client is None:
            final_state = await _run_loop(client=None)
            self._print_metrics()
            return final_state

        async with shared_client:
            final_state = await _run_loop(client=shared_client)

        self._print_metrics()
        return final_state
