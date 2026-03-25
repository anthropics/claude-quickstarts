from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from artifacts import ArtifactPaths
from builder import BuilderPhase
from evaluator import EvaluatorPhase


async def _empty_runner(project_dir: Path, model: str, prompt: str, phase: str, client=None) -> str:
    del project_dir, model, prompt, phase, client
    return "   "


async def _invalid_json_eval_runner(project_dir: Path, model: str, prompt: str, phase: str, client=None) -> str:
    del model, prompt, phase, client
    paths = ArtifactPaths(project_dir)
    paths.ensure_dirs()
    paths.qa_report_json(1).write_text("{ invalid")
    return "eval done"


async def _missing_report_eval_runner(project_dir: Path, model: str, prompt: str, phase: str, client=None) -> str:
    del project_dir, model, prompt, phase, client
    return "eval done"


def test_builder_empty_response_raises(tmp_path: Path) -> None:
    phase = BuilderPhase(_empty_runner)
    with pytest.raises(RuntimeError, match="empty response"):
        asyncio.run(
            phase.run(
                tmp_path,
                model="m",
                round_number=1,
                sprint_contract_path=tmp_path / "planning" / "sprint_contract_round_01.json",
            )
        )


def test_evaluator_invalid_json_uses_blocked_fallback(tmp_path: Path) -> None:
    phase = EvaluatorPhase(_invalid_json_eval_runner)
    contract = ArtifactPaths(tmp_path).sprint_contract_json(1)
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(
        '{"round_number":1,"features_in_scope":["x"],"acceptance_tests":[{"id":"A","criterion":"c","verification_method":"m"}]}'
    )
    result = asyncio.run(phase.run(tmp_path, model="m", round_number=1, sprint_contract_path=contract))
    assert result.result == "blocked"


def test_evaluator_missing_report_uses_blocked_fallback(tmp_path: Path) -> None:
    phase = EvaluatorPhase(_missing_report_eval_runner)
    contract = ArtifactPaths(tmp_path).sprint_contract_json(1)
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(
        '{"round_number":1,"features_in_scope":["x"],"acceptance_tests":[{"id":"A","criterion":"c","verification_method":"m"}]}'
    )
    result = asyncio.run(phase.run(tmp_path, model="m", round_number=1, sprint_contract_path=contract))
    assert result.result == "blocked"
