"""Builder phase for autonomous coding V2."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from artifacts import ArtifactPaths
from prompts import get_builder_prompt

PhaseRunner = Callable[[Path, str, str, str], Awaitable[str]]


@dataclass
class BuilderResult:
    report_path: Path
    summary: str


class BuilderPhase:
    """Runs a build round and emits deterministic round report artifacts."""

    def __init__(self, runner: PhaseRunner):
        self.runner = runner

    async def run(self, project_dir: Path, model: str, round_number: int) -> BuilderResult:
        paths = ArtifactPaths(project_dir)
        paths.ensure_dirs()
        summary = await self.runner(project_dir, model, get_builder_prompt(), "builder")
        report_path = paths.build_report_md(round_number)
        if not report_path.exists():
            report_path.write_text(
                f"# Build Report Round {round_number:02d}\n\n{summary.strip() or 'No summary from builder.'}\n"
            )
        return BuilderResult(report_path=report_path, summary=summary)
