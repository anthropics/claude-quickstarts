import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import constants

APP = Path(__file__).resolve().parents[1] / "dev_ui" / "trajectory_viewer" / "app.py"


@pytest.mark.parametrize("turn_count", [None, 0, 1, 2])
def test_viewer_handles_short_trajectories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, turn_count: int | None
) -> None:
    monkeypatch.chdir(tmp_path)
    runs = tmp_path / "runs"
    monkeypatch.setattr(constants, "RUNS_DIR", runs)
    run = runs / "20261109-120000"
    run.mkdir(parents=True)
    (run / "meta.json").write_text('{"task": "Example"}', encoding="utf-8")
    if turn_count is not None:
        entry = json.dumps({"role": "user", "content": "Example turn"})
        (run / "transcript.jsonl").write_text((entry + "\n") * turn_count, encoding="utf-8")

    app = AppTest.from_file(str(APP)).run()

    assert not app.exception
    assert len(app.chat_message) == (turn_count or 0)
    assert len(app.slider) == (1 if turn_count == 2 else 0)
    if not turn_count:
        assert app.info[0].value == "No turns recorded for this run."
