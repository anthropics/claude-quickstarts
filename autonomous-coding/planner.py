"""Planner phase for autonomous coding V3.4."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from claude_code_sdk import ClaudeSDKClient

from artifacts import ArtifactPaths, read_json, safe_validate, write_validated_json
from metrics import UsageEstimate, estimate_usage
from phase_types import PhaseRunner
from prompts import get_planner_prompt


@dataclass
class PlannerResult:
    summary: str
    usage: UsageEstimate


class PlannerPhase:
    """Runs planning and enforces required planning artifacts."""

    def __init__(self, runner: PhaseRunner, target_test_count: int = 200):
        self.runner = runner
        self.target_test_count = target_test_count

    def _validate_required_artifacts(self, paths: ArtifactPaths) -> tuple[dict[str, object], dict[str, object]]:
        errors: list[str] = []

        def load_required_json(path: Path, schema_name: str) -> dict[str, object]:
            if not path.exists():
                errors.append(f"{path.name} missing")
                return {}

            payload = read_json(path, context=schema_name)
            if not isinstance(payload, dict):
                errors.append(f"{path.name} must contain a JSON object")
                return {}

            ok, reason = safe_validate(payload, schema_name)
            if not ok:
                errors.append(f"{path.name} failed schema validation: {reason}")
                return {}

            return payload

        def validate_required_doc(path: Path) -> None:
            if not path.exists():
                errors.append(f"{path.name} missing")
                return

            content = path.read_text().strip()
            if not content:
                errors.append(f"{path.name} is empty")
                return
            if "Planner output pending." in content:
                errors.append(f"{path.name} contains placeholder content")

        acceptance = load_required_json(paths.acceptance_criteria, "acceptance_criteria")
        backlog = load_required_json(paths.work_backlog, "work_backlog")
        validate_required_doc(paths.expanded_spec)
        validate_required_doc(paths.architecture)

        if errors:
            details = "; ".join(errors)
            raise RuntimeError(
                "PlannerPhase required planning artifacts are missing, invalid, or placeholder: "
                f"{details}"
            )

        return acceptance, backlog

    async def run(self, project_dir: Path, model: str, client: ClaudeSDKClient | None = None) -> PlannerResult:
        paths = ArtifactPaths(project_dir)
        paths.ensure_dirs()
        prompt = get_planner_prompt(target_test_count=self.target_test_count)
        summary = await self.runner(project_dir, model, prompt, "planner", client)
        usage = estimate_usage(prompt, summary)
        print(
            "[V3.6.3] LLM call planner "
            f"tokens(in={usage.input_tokens},out={usage.output_tokens},total={usage.total_tokens}) "
            f"est_cost=${usage.estimated_cost_usd:.6f}"
        )

        acceptance, backlog = self._validate_required_artifacts(paths)
        write_validated_json(paths.acceptance_criteria, acceptance, "acceptance_criteria")
        write_validated_json(paths.work_backlog, backlog, "work_backlog")

        return PlannerResult(summary=summary, usage=usage)
