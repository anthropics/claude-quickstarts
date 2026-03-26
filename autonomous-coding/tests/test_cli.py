from __future__ import annotations

from pathlib import Path

import autonomous_agent_demo as cli


def test_parse_args_defaults(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["prog"])
    args = cli.parse_args()
    assert args.mode == "v3_1"
    assert args.max_rounds == 3
    assert args.llm_contract_review is False


def test_parse_args_model_override(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["prog", "--model", "claude-opus-4-6", "--max-rounds", "2"],
    )
    args = cli.parse_args()
    assert args.model == "claude-opus-4-6"
    assert args.max_rounds == 2


def test_parse_args_llm_contract_review_enabled(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["prog", "--llm-contract-review"])
    args = cli.parse_args()
    assert args.llm_contract_review is True


def test_normalize_project_dir_handles_dot_prefix() -> None:
    normalized = cli._normalize_project_dir(Path("./generations/myproject"))
    assert normalized == Path("generations/myproject")


def test_main_warns_when_v2_mode_is_used(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["prog", "--mode", "v2", "--project-dir", "./tmp-project", "--dry-run", "--max-rounds", "1"],
    )
    cli.main()
    output = capsys.readouterr().out
    assert "deprecated and aliased to v3_1" in output
