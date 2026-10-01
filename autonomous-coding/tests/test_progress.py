from __future__ import annotations

import json
from pathlib import Path

from progress import count_passing_tests, print_progress_summary


def test_count_passing_tests_returns_safe_fallback_for_unexpected_mapping(tmp_path: Path) -> None:
    (tmp_path / "feature_list.json").write_text(json.dumps({"items": []}))

    assert count_passing_tests(tmp_path) == (0, 0)


def test_print_progress_summary_handles_unexpected_run_state_shape(tmp_path: Path, capsys) -> None:
    (tmp_path / "feature_list.json").write_text(json.dumps({"items": []}))
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "run_state.json").write_text(json.dumps([1, 2, 3]))

    print_progress_summary(tmp_path)

    output = capsys.readouterr().out
    assert "Run State: unexpected run_state.json structure" in output
    assert "Backlog progress: feature_list.json not yet created" in output
