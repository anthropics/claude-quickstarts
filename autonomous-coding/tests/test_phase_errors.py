from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from artifacts import ArtifactPaths, write_validated_json
from builder import BuilderPhase
from evaluator import EvaluatorPhase
from planner import PlannerPhase


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


async def _schema_invalid_eval_runner(project_dir: Path, model: str, prompt: str, phase: str, client=None) -> str:
    del model, prompt, phase, client
    paths = ArtifactPaths(project_dir)
    paths.ensure_dirs()
    paths.qa_report_json(1).write_text(
        '{"round":1,"result":"unknown","summary":"bad","blocking_findings":[]}'
    )
    return "eval done"


async def _missing_planner_artifacts_runner(
    project_dir: Path, model: str, prompt: str, phase: str, client=None
) -> str:
    del project_dir, model, prompt, phase, client
    return "planner done"


async def _placeholder_planner_docs_runner(
    project_dir: Path, model: str, prompt: str, phase: str, client=None
) -> str:
    del model, prompt, phase, client
    paths = ArtifactPaths(project_dir)
    paths.ensure_dirs()
    write_validated_json(
        paths.acceptance_criteria,
        {
            "project_name": project_dir.name,
            "criteria": [{"id": "AC-001", "description": "Real criterion", "priority": "p0"}],
        },
        "acceptance_criteria",
    )
    write_validated_json(
        paths.work_backlog,
        {
            "items": [
                {
                    "id": "WB-001",
                    "title": "Real backlog item",
                    "status": "todo",
                    "source_feature_index": 0,
                }
            ]
        },
        "work_backlog",
    )
    paths.expanded_spec.write_text("# Expanded Spec\n\nPlanner output pending.\n")
    paths.architecture.write_text("# Architecture\n\nPlanner output pending.\n")
    return "planner done"


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


def test_planner_missing_artifacts_raise_explicit_failure(tmp_path: Path) -> None:
    phase = PlannerPhase(_missing_planner_artifacts_runner)
    with pytest.raises(RuntimeError, match="required planning artifacts"):
        asyncio.run(phase.run(tmp_path, model="m"))


def test_planner_placeholder_docs_raise_explicit_failure(tmp_path: Path) -> None:
    phase = PlannerPhase(_placeholder_planner_docs_runner)
    with pytest.raises(RuntimeError, match="placeholder"):
        asyncio.run(phase.run(tmp_path, model="m"))


def test_evaluator_invalid_json_uses_blocked_fallback(tmp_path: Path) -> None:
    phase = EvaluatorPhase(_invalid_json_eval_runner)
    contract = ArtifactPaths(tmp_path).sprint_contract_json(1)
    write_validated_json(
        contract,
        {
            "round_number": 1,
            "features_in_scope": ["x"],
            "acceptance_tests": [{"id": "A", "criterion": "c", "verification_method": "m"}],
        },
        "sprint_contract",
    )
    result = asyncio.run(phase.run(tmp_path, model="m", round_number=1, sprint_contract_path=contract))
    assert result.result == "blocked"


def test_evaluator_missing_report_uses_blocked_fallback(tmp_path: Path) -> None:
    phase = EvaluatorPhase(_missing_report_eval_runner)
    contract = ArtifactPaths(tmp_path).sprint_contract_json(1)
    write_validated_json(
        contract,
        {
            "round_number": 1,
            "features_in_scope": ["x"],
            "acceptance_tests": [{"id": "A", "criterion": "c", "verification_method": "m"}],
        },
        "sprint_contract",
    )
    result = asyncio.run(phase.run(tmp_path, model="m", round_number=1, sprint_contract_path=contract))
    assert result.result == "blocked"


def test_evaluator_schema_invalid_report_uses_blocked_fallback(tmp_path: Path) -> None:
    phase = EvaluatorPhase(_schema_invalid_eval_runner)
    contract = ArtifactPaths(tmp_path).sprint_contract_json(1)
    write_validated_json(
        contract,
        {
            "round_number": 1,
            "features_in_scope": ["x"],
            "acceptance_tests": [{"id": "A", "criterion": "c", "verification_method": "m"}],
        },
        "sprint_contract",
    )
    result = asyncio.run(phase.run(tmp_path, model="m", round_number=1, sprint_contract_path=contract))
    assert result.result == "blocked"
