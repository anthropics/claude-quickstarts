from __future__ import annotations

import json
from pathlib import Path

from artifacts import ArtifactPaths, SCHEMA_DIR, safe_validate, write_validated_json
from state_models import RunState, RunStatus


def test_run_state_schema_roundtrip(tmp_path: Path) -> None:
    paths = ArtifactPaths(tmp_path)
    paths.ensure_dirs()
    state = RunState(max_rounds=5)
    payload = state.to_dict()
    ok, reason = safe_validate(payload, "run_state")
    assert ok, reason
    write_validated_json(paths.run_state, payload, "run_state")
    assert paths.run_state.exists()


def test_qa_schema_invalid() -> None:
    ok, _ = safe_validate({"round": 1, "result": "pass"}, "qa_report")
    assert not ok


def test_run_status_enum_matches_schema() -> None:
    schema = json.loads((SCHEMA_DIR / "run_state.schema.json").read_text())
    schema_values = set(schema["properties"]["status"]["enum"])
    code_values = {s.value for s in RunStatus}
    assert schema_values == code_values


def test_sprint_contract_schema_validates() -> None:
    payload = {
        "round_number": 1,
        "features_in_scope": ["Feature A"],
        "acceptance_tests": [
            {
                "id": "AC-001",
                "criterion": "User can complete a core flow",
                "verification_method": "Browser QA",
            }
        ],
    }
    ok, reason = safe_validate(payload, "sprint_contract")
    assert ok, reason


def test_sprint_contract_negotiation_schema_validates() -> None:
    payload = {
        "round_number": 2,
        "status": "approved",
        "max_turns": 2,
        "turns_used": 1,
        "feedback": [],
        "approved_features": ["Feature A"],
        "approved_acceptance_tests": [
            {
                "id": "AC-100",
                "criterion": "User can persist preference",
                "verification_method": "Browser QA",
            }
        ],
    }
    ok, reason = safe_validate(payload, "sprint_contract_negotiation")
    assert ok, reason
