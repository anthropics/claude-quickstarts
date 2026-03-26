"""Evaluator / QA phase for autonomous coding V3.2."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from claude_code_sdk import ClaudeSDKClient

from artifacts import ArtifactPaths, read_json, safe_validate, write_validated_json
from phase_types import PhaseRunner
from prompts import get_evaluator_prompt


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

    async def run(
        self,
        project_dir: Path,
        model: str,
        round_number: int,
        sprint_contract_path: Path,
        client: ClaudeSDKClient | None = None,
    ) -> EvaluatorResult:
        paths = ArtifactPaths(project_dir)
        paths.ensure_dirs()
        prompt = (
            f"{get_evaluator_prompt()}\n\n"
            f"Current round number: {round_number}\n"
            f"Sprint contract (mandatory oracle): {sprint_contract_path.as_posix()}\n"
        )
        summary = await self.runner(project_dir, model, prompt, "evaluator", client)

        report_json_path = paths.qa_report_json(round_number)
        fallback_report = {
            "round": round_number,
            "result": "blocked",
            "summary": "Evaluator report missing or malformed; treating as blocker.",
            "blocking_findings": [
                {
                    "id": f"QA-{round_number:02d}-001",
                    "severity": "critical",
                    "description": "QA artifact missing or invalid JSON.",
                    "repro_steps": ["Run evaluator phase and inspect qa artifact generation."],
                }
            ],
        }
        report = read_json(report_json_path, default=fallback_report, context="qa_report")
        if "result" not in report:
            report = fallback_report

        ok, reason = safe_validate(report, "qa_report")
        if not ok:
            print(f"[V3.2] QA report failed schema validation: {reason}. Using blocked fallback.")
            report = fallback_report

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
