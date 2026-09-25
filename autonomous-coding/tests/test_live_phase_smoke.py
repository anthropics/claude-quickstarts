from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path

import pytest

import builder as builder_module
import evaluator as evaluator_module
import planner as planner_module
from artifacts import ArtifactPaths, write_validated_json
from builder import BuilderPhase
from evaluator import EvaluatorPhase
from orchestrator import ModelConfig, Orchestrator
from planner import PlannerPhase
from agent import run_phase_session

pytestmark = pytest.mark.live

LIVE_FLAG = "AUTONOMOUS_CODING_ENABLE_LIVE_TESTS"
LIVE_MODEL_ENV = "AUTONOMOUS_CODING_LIVE_MODEL"
LIVE_ARTIFACT_ROOT_ENV = "AUTONOMOUS_CODING_LIVE_ARTIFACT_ROOT"


def _require_live_execution() -> None:
    if os.environ.get(LIVE_FLAG) != "1":
        pytest.skip(f"set {LIVE_FLAG}=1 to run live SDK smoke tests")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY is required for live SDK smoke tests")


def _live_model() -> str:
    return os.environ.get(LIVE_MODEL_ENV, "claude-opus-4-6")


def _project_dir(tmp_path: Path, name: str) -> Path:
    artifact_root = Path(os.environ.get(LIVE_ARTIFACT_ROOT_ENV, str(tmp_path)))
    project_dir = artifact_root / name
    if project_dir.exists():
        shutil.rmtree(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def test_planner_phase_live_writes_required_artifacts(monkeypatch, tmp_path: Path) -> None:
    _require_live_execution()
    project_dir = _project_dir(tmp_path, "planner-live")
    monkeypatch.setattr(
        planner_module,
        "get_planner_prompt",
        lambda target_test_count=200: (
            "Write these required planning artifacts exactly and then stop.\n"
            "- planning/acceptance_criteria.json valid schema with one p0 criterion AC-LIVE-001.\n"
            "- planning/work_backlog.json valid schema with one todo item WB-LIVE-001.\n"
            "- planning/expanded_spec.md with non-placeholder text.\n"
            "- planning/architecture.md with non-placeholder text.\n"
            "Return one short summary line after writing the files."
        ),
    )

    result = asyncio.run(PlannerPhase(run_phase_session).run(project_dir, model=_live_model()))
    paths = ArtifactPaths(project_dir)
    acceptance = json.loads(paths.acceptance_criteria.read_text(encoding="utf-8"))
    backlog = json.loads(paths.work_backlog.read_text(encoding="utf-8"))

    assert "summary" not in result.summary.lower()
    assert acceptance["criteria"][0]["id"] == "AC-LIVE-001"
    assert backlog["items"][0]["id"] == "WB-LIVE-001"
    assert "placeholder" not in paths.expanded_spec.read_text(encoding="utf-8").lower()
    assert "placeholder" not in paths.architecture.read_text(encoding="utf-8").lower()


def test_builder_phase_live_writes_report_and_proposal(monkeypatch, tmp_path: Path) -> None:
    _require_live_execution()
    project_dir = _project_dir(tmp_path, "builder-live")
    paths = ArtifactPaths(project_dir)
    paths.ensure_dirs()
    contract = paths.sprint_contract_json(1)
    write_validated_json(
        contract,
        {
            "round_number": 1,
            "features_in_scope": ["Ship one visible smoke-test placeholder"],
            "acceptance_tests": [
                {
                    "id": "AC-LIVE-BUILD-001",
                    "criterion": "Builder writes the next-round proposal artifact.",
                    "verification_method": "Inspect planning/sprint_proposal_round_01.md",
                }
            ],
        },
        "sprint_contract",
    )
    monkeypatch.setattr(
        builder_module,
        "get_builder_prompt",
        lambda: (
            "Read the sprint contract and write planning/sprint_proposal_round_01.md.\n"
            "Use this exact structure:\n"
            "# Sprint Proposal Round 01\n\n"
            "## Proposed features in scope\n"
            "- Smoke-test follow-up feature\n\n"
            "## Proposed acceptance tests\n"
            "- AC-LIVE-NEXT-001 | Follow-up criterion | Inspect the proposal file\n"
            "Do not use browser tools. Return one short summary line."
        ),
    )

    result = asyncio.run(
        BuilderPhase(run_phase_session).run(
            project_dir,
            model=_live_model(),
            round_number=1,
            sprint_contract_path=contract,
        )
    )

    proposal_path = paths.sprint_proposal_md(1)
    assert result.report_path.exists()
    assert proposal_path.exists()
    assert "AC-LIVE-NEXT-001" in proposal_path.read_text(encoding="utf-8")


def test_evaluator_phase_live_writes_valid_qa_report(monkeypatch, tmp_path: Path) -> None:
    _require_live_execution()
    project_dir = _project_dir(tmp_path, "evaluator-live")
    paths = ArtifactPaths(project_dir)
    paths.ensure_dirs()
    contract = paths.sprint_contract_json(1)
    write_validated_json(
        contract,
        {
            "round_number": 1,
            "features_in_scope": ["Smoke evaluator artifact"],
            "acceptance_tests": [
                {
                    "id": "AC-LIVE-QA-001",
                    "criterion": "Evaluator writes a valid QA report.",
                    "verification_method": "Inspect qa/qa_report_round_01.json",
                }
            ],
        },
        "sprint_contract",
    )
    monkeypatch.setattr(
        evaluator_module,
        "get_evaluator_prompt",
        lambda: (
            "Do not use browser tools for this smoke test.\n"
            "Write qa/qa_report_round_01.json with valid schema.\n"
            "Use result='blocked', summary='Live evaluator smoke report', and one critical blocking finding.\n"
            "Return one short summary line after writing the JSON."
        ),
    )

    result = asyncio.run(
        EvaluatorPhase(run_phase_session).run(
            project_dir,
            model=_live_model(),
            round_number=1,
            sprint_contract_path=contract,
        )
    )
    report = json.loads(paths.qa_report_json(1).read_text(encoding="utf-8"))

    assert result.report_json_path.exists()
    assert report["result"] == "blocked"
    assert report["summary"] == "Live evaluator smoke report"
    assert report["blocking_findings"][0]["id"] == "QA-LIVE-001"
    assert "missing or malformed" not in report["summary"].lower()


def test_contract_reviewer_live_returns_structured_json(tmp_path: Path) -> None:
    _require_live_execution()
    project_dir = _project_dir(tmp_path, "contract-review-live")
    orchestrator = Orchestrator(
        project_dir=project_dir,
        model_config=ModelConfig(_live_model(), _live_model(), _live_model()),
        max_rounds=2,
        phase_runner=run_phase_session,
        llm_contract_review=True,
    )

    review = asyncio.run(
        orchestrator._review_proposal_and_write_negotiation(
            round_number=2,
            proposed_features=["Keep scope limited to one smoke-test feature"],
            proposed_acceptance=[
                {
                    "id": "AC-LIVE-REVIEW-001",
                    "criterion": "Response stays in JSON and within schema.",
                    "verification_method": "Inspect negotiation artifact",
                }
            ],
            parse_issues=[],
        )
    )

    artifact = json.loads(ArtifactPaths(project_dir).sprint_contract_negotiation_json(2).read_text(encoding="utf-8"))
    assert review["status"] in {"approved", "changes_requested"}
    assert artifact["review_mode"] == "llm_assisted"
    assert "LLM_RESPONSE_INVALID" not in artifact.get("reason_codes", [])
