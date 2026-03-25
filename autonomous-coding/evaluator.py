"""Evaluator / QA phase for autonomous coding V2."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

from artifacts import ArtifactPaths, read_json, write_validated_json
from prompts import get_evaluator_prompt

PhaseRunner = Callable[[Path, str, str, str], Awaitable[str]]


@dataclass
class EvaluatorResult:
    result: str
    report_json_path: Path
    report_md_path: Path
    blocking_issues: list[str]
    summary: str


class EvaluatorPhase:
    """Runs browser-focused QA and writes structured QA reports."""

    def __init__(self, runner: PhaseRunner):
        self.runner = runner

    async def run(self, project_dir: Path, model: str, round_number: int) -> EvaluatorResult:
        paths = ArtifactPaths(project_dir)
        paths.ensure_dirs()
        summary = await self.runner(project_dir, model, get_evaluator_prompt(), "evaluator")

        report_json_path = paths.qa_report_json(round_number)
        report = read_json(report_json_path)
        if not report:
            report = {
                "round": round_number,
                "result": "blocked",
                "summary": "Evaluator did not produce structured QA report; treating as blocker.",
                "blocking_findings": [
                    {
                        "id": f"QA-{round_number:02d}-001",
                        "severity": "critical",
                        "description": "Missing QA artifact output.",
                        "repro_steps": ["Run evaluator phase and inspect qa report generation."],
                    }
                ],
            }
        write_validated_json(report_json_path, report, "qa_report")

        report_md_path = paths.qa_report_md(round_number)
        if not report_md_path.exists():
            report_md_path.write_text(
                f"# QA Report Round {round_number:02d}\n\nResult: **{report['result']}**\n\n{report['summary']}\n"
            )

        issues = [finding["description"] for finding in report.get("blocking_findings", [])]
        return EvaluatorResult(
            result=report["result"],
            report_json_path=report_json_path,
            report_md_path=report_md_path,
            blocking_issues=issues,
            summary=summary or report.get("summary", ""),
        )
