#!/usr/bin/env python3
"""Autonomous coding harness entrypoint (V3.6.1 runtime, V1 compatibility mode)."""

from __future__ import annotations

import argparse
import asyncio
from functools import partial
from pathlib import Path

from agent import run_autonomous_agent, run_phase_session
from client import create_client, validate_auth_configuration
from orchestrator import ModelConfig, Orchestrator
from progress import print_progress_summary
from prompts import copy_spec_to_project

DEFAULT_MODEL = "claude-opus-4-6"
DEFAULT_PLANNER_MODEL = "claude-opus-4-6"
DEFAULT_BUILDER_MODEL = "claude-opus-4-6"
DEFAULT_EVALUATOR_MODEL = "claude-opus-4-6"


class _DryRunClient:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _dry_run_client_factory(project_dir: Path, model: str, phase: str):
    del project_dir, model, phase
    return _DryRunClient()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autonomous Coding Harness")
    parser.add_argument("--project-dir", type=Path, default=Path("./autonomous_demo_project"))
    parser.add_argument("--mode", choices=["v3_1", "v2", "v1"], default="v3_1")

    parser.add_argument("--model", type=str, default=None, help="Single model override for all phases")
    parser.add_argument("--planner-model", type=str, default=DEFAULT_PLANNER_MODEL)
    parser.add_argument("--builder-model", type=str, default=DEFAULT_BUILDER_MODEL)
    parser.add_argument("--evaluator-model", type=str, default=DEFAULT_EVALUATOR_MODEL)

    parser.add_argument("--max-rounds", type=int, default=3)
    parser.add_argument("--max-iterations", type=int, default=None, help="V1 mode only")
    parser.add_argument(
        "--target-tests",
        type=int,
        default=None,
        help="Target minimum test count for planning/initialization prompts across modes (default: 200).",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--planner-only", action="store_true")
    parser.add_argument("--qa-only", action="store_true")
    parser.add_argument(
        "--auth-mode",
        choices=["api_key", "cli", "auto"],
        default="api_key",
        help="Authentication mode for Claude SDK client",
    )
    parser.add_argument(
        "--llm-contract-review",
        action="store_true",
        help="Enable optional evaluator-model arbitration during sprint contract negotiation.",
    )
    return parser.parse_args()


def _normalize_project_dir(project_dir: Path) -> Path:
    if project_dir.is_absolute():
        return project_dir

    cleaned_parts = [part for part in project_dir.parts if part not in {".", ""}]
    cleaned = Path(*cleaned_parts) if cleaned_parts else Path(".")
    if cleaned.parts and cleaned.parts[0] == "generations":
        return cleaned

    return Path("generations") / cleaned


async def _run_v3_1(args: argparse.Namespace, project_dir: Path) -> None:
    copy_spec_to_project(project_dir)

    if args.model:
        model_config = ModelConfig(args.model, args.model, args.model)
    else:
        model_config = ModelConfig(
            planner_model=args.planner_model,
            builder_model=args.builder_model,
            evaluator_model=args.evaluator_model,
        )

    if args.dry_run:

        async def dry_runner(
            project_dir: Path,
            model: str,
            prompt: str,
            phase: str,
            client=None,
        ) -> str:
            del prompt, client
            return f"[dry-run] phase={phase} model={model} project={project_dir}"

        runner = dry_runner
    else:
        runner = run_phase_session

    orchestrator_kwargs = {}
    if args.dry_run:
        orchestrator_kwargs["client_factory"] = _dry_run_client_factory
    else:
        orchestrator_kwargs["client_factory"] = partial(create_client, auth_mode=args.auth_mode)

    orchestrator = Orchestrator(
        project_dir=project_dir,
        model_config=model_config,
        max_rounds=args.max_rounds,
        phase_runner=runner,
        llm_contract_review=args.llm_contract_review,
        target_test_count=args.target_tests or 200,
        **orchestrator_kwargs,
    )
    state = await orchestrator.run(
        resume=args.resume,
        planner_only=args.planner_only,
        qa_only=args.qa_only,
    )
    print(f"Final status: {state.status.value}, completed={state.completed}")
    print_progress_summary(project_dir)


def main() -> None:
    args = parse_args()
    target_tests = args.target_tests
    if target_tests is None:
        target_tests = 200
        print("[WARNING] --target-tests not provided; defaulting to 200.")
    elif target_tests <= 0:
        print("Error: --target-tests must be a positive integer.")
        return

    if not args.dry_run:
        try:
            validate_auth_configuration(args.auth_mode)
        except ValueError as exc:
            print(f"Error: {exc}")
            return

    project_dir = _normalize_project_dir(args.project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)

    try:
        if args.mode == "v1":
            model = args.model or DEFAULT_MODEL
            asyncio.run(
                run_autonomous_agent(
                    project_dir=project_dir,
                    model=model,
                    max_iterations=args.max_iterations,
                    auth_mode=args.auth_mode,
                    target_test_count=target_tests,
                )
            )
        elif args.mode == "v2":
            print(
                "[WARNING] --mode v2 is deprecated and aliased to v3_1. "
                "Use --mode v3_1 explicitly. This alias will be removed in a future release."
            )
            asyncio.run(_run_v3_1(args, project_dir))
        else:
            asyncio.run(_run_v3_1(args, project_dir))
    except KeyboardInterrupt:
        print("\nInterrupted by user. Re-run with --resume to continue.")


if __name__ == "__main__":
    main()
