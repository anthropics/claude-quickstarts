"""Planner phase for autonomous coding V3.1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from claude_code_sdk import ClaudeSDKClient

from artifacts import ArtifactPaths, read_json, write_validated_json
from phase_types import PhaseRunner
from prompts import get_planner_prompt


@dataclass
class PlannerResult:
    summary: str


class PlannerPhase:
    """Runs planning and enforces required planning artifacts."""

    def __init__(self, runner: PhaseRunner):
        self.runner = runner

    async def run(self, project_dir: Path, model: str, client: ClaudeSDKClient | None = None) -> PlannerResult:
        paths = ArtifactPaths(project_dir)
        paths.ensure_dirs()
        summary = await self.runner(project_dir, model, get_planner_prompt(), "planner", client)

        acceptance = read_json(paths.acceptance_criteria, context="acceptance_criteria")
        if not acceptance:
            acceptance = {
                "project_name": project_dir.name,
                "criteria": [
                    {
                        "id": "AC-001",
                        "description": "Core application boots and basic chat flow works.",
                        "priority": "p0",
                    }
                ],
            }
        write_validated_json(paths.acceptance_criteria, acceptance, "acceptance_criteria")

        backlog = read_json(paths.work_backlog, context="work_backlog")
        if not backlog:
            backlog = {
                "items": [
                    {
                        "id": "WB-001",
                        "title": "Establish initial working vertical slice",
                        "status": "todo",
                        "source_feature_index": 0,
                    }
                ]
            }
        write_validated_json(paths.work_backlog, backlog, "work_backlog")

        for doc_path, default in [
            (paths.expanded_spec, "# Expanded Spec\n\nPlanner output pending.\n"),
            (paths.architecture, "# Architecture\n\nPlanner output pending.\n"),
        ]:
            if not doc_path.exists():
                doc_path.write_text(default)

        return PlannerResult(summary=summary)
