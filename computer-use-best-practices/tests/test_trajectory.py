import base64
import datetime as dt
import json

from computer_use import trajectory


def test_same_second_runs_do_not_overwrite_each_other(tmp_path, monkeypatch):
    class FixedDatetime(dt.datetime):
        @classmethod
        def now(cls):
            return cls(2026, 1, 1, 12, 0, 0)

    monkeypatch.setattr(trajectory.dt, "datetime", FixedDatetime)
    monkeypatch.setattr(trajectory, "RUNS_DIR", tmp_path / "runs")
    first = trajectory.Trajectory("example-model", "first")
    first_image = first.save_image(base64.b64encode(b"first-image").decode())
    first.record("user", "first transcript")
    second = trajectory.Trajectory("example-model", "second")
    second_image = second.save_image(base64.b64encode(b"second-image").decode())
    second.record("user", "second transcript")
    assert first.dir != second.dir
    assert first.dir.name.startswith("20260101-120000")
    assert json.loads((first.dir / "meta.json").read_text())["task"] == "first"
    assert (first.dir / first_image).read_bytes() == b"first-image"
    assert (second.dir / second_image).read_bytes() == b"second-image"
    assert len((first.dir / "transcript.jsonl").read_text().splitlines()) == 1
