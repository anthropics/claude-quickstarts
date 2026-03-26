"""Builder phase for autonomous coding V3.1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from artifacts import ArtifactPaths
from phase_types import PhaseRunner
from prompts import get_builder_prompt


@dataclass
class BuilderResult:
    report_path: Path
    summary: str


class BuilderPhase:
    """Runs a build round and emits deterministic round report artifacts."""

    def __init__(self, runner: PhaseRunner):
        self.runner = runner

    async def run(
        self,
        project_dir: Path,
        model: str,
        round_number: int,
        sprint_contract_path: Path,
        client: ClaudeSDKClient | None = None,
    ) -> BuilderResult:
        paths = ArtifactPaths(project_dir)
        paths.ensure_dirs()
        prompt = (
            f"{get_builder_prompt()}\n\n"
            f"Current round number: {round_number}\n"
            f"Sprint contract (must be honored): {sprint_contract_path.as_posix()}\n"
            "After implementation, write planning/sprint_proposal_round_XX.md for the next round "
            "using the template in the builder prompt.\n"
        )
        summary = await self.runner(project_dir, model, prompt, "builder", client)
        if not summary or not summary.strip():
            raise RuntimeError(
                f"BuilderPhase round {round_number}: runner returned empty response. "
                "Builder may have failed silently."
            )

        report_path = paths.build_report_md(round_number)
        if not report_path.exists():
            report_path.write_text(f"# Build Report Round {round_number:02d}\n\n{summary.strip()}\n")
        return BuilderResult(report_path=report_path, summary=summary)
