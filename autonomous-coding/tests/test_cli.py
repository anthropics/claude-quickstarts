from __future__ import annotations

import autonomous_agent_demo as cli


def test_parse_args_defaults(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["prog"])
    args = cli.parse_args()
    assert args.mode == "v2"
    assert args.max_rounds == 3


def test_parse_args_model_override(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["prog", "--model", "claude-sonnet-4-6", "--max-rounds", "2"],
    )
    args = cli.parse_args()
    assert args.model == "claude-sonnet-4-6"
    assert args.max_rounds == 2
