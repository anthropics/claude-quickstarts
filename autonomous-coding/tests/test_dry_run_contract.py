from __future__ import annotations

import json

import autonomous_agent_demo as cli
from artifacts import ArtifactPaths


def _fail_if_called(*args, **kwargs):
    del args, kwargs
    raise AssertionError("live auth/client path should be bypassed in dry-run")


def test_orchestrated_dry_run_generates_expected_offline_artifacts(monkeypatch, tmp_path, capsys) -> None:
    project_dir = tmp_path / "offline-dry-run"
    monkeypatch.setattr(
        "sys.argv",
        [
            "prog",
            "--mode",
            "orchestrated",
            "--project-dir",
            str(project_dir),
            "--dry-run",
            "--max-rounds",
            "1",
        ],
    )
    monkeypatch.setattr(cli, "validate_auth_configuration", _fail_if_called)
    monkeypatch.setattr(cli, "create_client", _fail_if_called)

    cli.main()

    output = capsys.readouterr().out
    paths = ArtifactPaths(project_dir)
    acceptance = json.loads(paths.acceptance_criteria.read_text())
    backlog = json.loads(paths.work_backlog.read_text())
    qa_report = json.loads(paths.qa_report_json(1).read_text())
    run_state = json.loads(paths.run_state.read_text())
    round_state = json.loads(paths.round_state(1).read_text())

    assert "Final status: blocked, completed=False" in output
    assert acceptance["criteria"][0]["id"] == "AC-DRYRUN-001"
    assert backlog["items"][0]["id"] == "WB-DRYRUN-001"
    assert paths.expanded_spec.read_text(encoding="utf-8").strip().endswith("Dry-run planner artifact.")
    assert paths.architecture.read_text(encoding="utf-8").strip().endswith("Dry-run planner artifact.")
    assert paths.sprint_contract_json(1).exists()
    assert paths.build_report_md(1).exists()
    assert qa_report["result"] == "blocked"
    assert qa_report["summary"] == "Evaluator report missing or malformed; treating as blocker."
    assert run_state["planner_complete"] is True
    assert run_state["current_round"] == 1
    assert run_state["status"] == "blocked"
    assert round_state["builder_report_path"].endswith("build_report_round_01.md")
    assert round_state["evaluator_report_json_path"].endswith("qa_report_round_01.json")


def test_orchestrated_dry_run_contract_review_records_live_gap(monkeypatch, tmp_path) -> None:
    project_dir = tmp_path / "offline-contract-review"
    monkeypatch.setattr(
        "sys.argv",
        [
            "prog",
            "--mode",
            "orchestrated",
            "--project-dir",
            str(project_dir),
            "--dry-run",
            "--max-rounds",
            "2",
            "--llm-contract-review",
        ],
    )
    monkeypatch.setattr(cli, "validate_auth_configuration", _fail_if_called)
    monkeypatch.setattr(cli, "create_client", _fail_if_called)

    cli.main()

    paths = ArtifactPaths(project_dir)
    negotiation = json.loads(paths.sprint_contract_negotiation_json(2).read_text())
    run_state = json.loads(paths.run_state.read_text())

    assert negotiation["review_mode"] == "llm_assisted"
    assert "LLM_ARBITRATION_REQUESTED" in negotiation["reason_codes"]
    assert "LLM_RESPONSE_INVALID" in negotiation["reason_codes"]
    assert negotiation["turns_used"] == 2
    assert run_state["current_round"] == 2
    assert run_state["status"] == "blocked"
