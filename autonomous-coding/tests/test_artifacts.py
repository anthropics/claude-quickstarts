from __future__ import annotations

from pathlib import Path

from artifacts import ArtifactPaths, safe_validate, write_validated_json
from state_models import RunState


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
