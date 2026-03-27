from __future__ import annotations

from pathlib import Path

import autonomous_agent_demo as cli


def test_parse_args_defaults(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["prog"])
    args = cli.parse_args()
    assert args.mode == "v3_1"
    assert args.max_rounds == 3
    assert args.target_tests is None
    assert args.auth_mode == "api_key"
    assert args.llm_contract_review is False


def test_parse_args_model_override(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["prog", "--model", "claude-opus-4-6", "--max-rounds", "2"],
    )
    args = cli.parse_args()
    assert args.model == "claude-opus-4-6"
    assert args.max_rounds == 2


def test_parse_args_target_tests_override(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["prog", "--target-tests", "350"])
    args = cli.parse_args()
    assert args.target_tests == 350


def test_parse_args_llm_contract_review_enabled(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["prog", "--llm-contract-review"])
    args = cli.parse_args()
    assert args.llm_contract_review is True


def test_parse_args_auth_mode_cli(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["prog", "--auth-mode", "cli"])
    args = cli.parse_args()
    assert args.auth_mode == "cli"


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


def test_main_warns_when_target_tests_default_is_used(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["prog", "--mode", "v1", "--project-dir", "./tmp-project", "--max-iterations", "0", "--dry-run"],
    )
    async def fake_run_autonomous_agent(*args, **kwargs):
        return None

    monkeypatch.setattr(cli, "run_autonomous_agent", fake_run_autonomous_agent)
    cli.main()
    output = capsys.readouterr().out
    assert "--target-tests not provided; defaulting to 200" in output


def test_main_rejects_non_positive_target_tests(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["prog", "--target-tests", "0", "--dry-run"])
    cli.main()
    output = capsys.readouterr().out
    assert "--target-tests must be a positive integer" in output


def test_main_rejects_missing_cli_credentials(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["prog", "--auth-mode", "cli", "--project-dir", "./tmp-project"])
    monkeypatch.delenv("CLAUDE_CODE_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("CLAUDE_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(cli, "_run_v3_1", lambda *args, **kwargs: None)
    cli.main()
    output = capsys.readouterr().out
    assert "Claude CLI credentials were not detected" in output
