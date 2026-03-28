from __future__ import annotations

from pathlib import Path

import pytest

import autonomous_agent_demo as cli


def test_parse_args_defaults(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["prog"])
    args = cli.parse_args()
    assert args.mode == "orchestrated"
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


def test_parse_args_accepts_legacy_mode(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["prog", "--mode", "legacy"])
    args = cli.parse_args()
    assert args.mode == "legacy"


def test_parse_args_rejects_v2_mode(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["prog", "--mode", "v2"])
    with pytest.raises(SystemExit):
        cli.parse_args()
    output = capsys.readouterr().err
    assert "unsupported mode 'v2'" in output


def test_parse_args_help_shows_official_modes_without_v2(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["prog", "--help"])
    with pytest.raises(SystemExit):
        cli.parse_args()
    output = capsys.readouterr().out
    assert "{legacy,orchestrated}" in output
    assert "v2" not in output


def test_normalize_project_dir_handles_dot_prefix() -> None:
    normalized = cli._normalize_project_dir(Path("./generations/myproject"))
    assert normalized == Path("generations/myproject")


@pytest.mark.parametrize("raw_path", ["../x", "safe/../x"])
def test_normalize_project_dir_rejects_parent_traversal(raw_path: str) -> None:
    with pytest.raises(ValueError, match="must stay within generations"):
        cli._normalize_project_dir(Path(raw_path))


def test_main_dispatches_legacy_mode(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["prog", "--mode", "legacy", "--project-dir", "./tmp-project", "--max-iterations", "0", "--dry-run"],
    )
    called = {"legacy": False}

    async def fake_run_autonomous_agent(*args, **kwargs):
        called["legacy"] = True
        return None

    monkeypatch.setattr(cli, "run_autonomous_agent", fake_run_autonomous_agent)
    cli.main()
    output = capsys.readouterr().out
    assert called["legacy"] is True
    assert "deprecated alias" not in output


def test_main_warns_when_v1_alias_is_used(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["prog", "--mode", "v1", "--project-dir", "./tmp-project", "--max-iterations", "0", "--dry-run"],
    )
    called = {"legacy": False}

    async def fake_run_autonomous_agent(*args, **kwargs):
        called["legacy"] = True
        return None

    monkeypatch.setattr(cli, "run_autonomous_agent", fake_run_autonomous_agent)
    cli.main()
    output = capsys.readouterr().out
    assert called["legacy"] is True
    assert "deprecated alias for legacy" in output


def test_main_warns_when_target_tests_default_is_used(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["prog", "--mode", "legacy", "--project-dir", "./tmp-project", "--max-iterations", "0", "--dry-run"],
    )
    async def fake_run_autonomous_agent(*args, **kwargs):
        return None

    monkeypatch.setattr(cli, "run_autonomous_agent", fake_run_autonomous_agent)
    cli.main()
    output = capsys.readouterr().out
    assert "--target-tests not provided; defaulting to 200" in output


def test_main_dispatches_orchestrated_mode(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["prog", "--mode", "orchestrated", "--project-dir", "./tmp-project", "--dry-run"])
    called = {"orchestrated": False}

    async def fake_run_orchestrated(*args, **kwargs):
        called["orchestrated"] = True
        return None

    monkeypatch.setattr(cli, "_run_orchestrated", fake_run_orchestrated)
    cli.main()
    output = capsys.readouterr().out
    assert called["orchestrated"] is True
    assert "deprecated alias" not in output


def test_main_warns_when_v3_1_alias_is_used(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["prog", "--mode", "v3_1", "--project-dir", "./tmp-project", "--dry-run"])
    called = {"orchestrated": False}

    async def fake_run_orchestrated(*args, **kwargs):
        called["orchestrated"] = True
        return None

    monkeypatch.setattr(cli, "_run_orchestrated", fake_run_orchestrated)
    cli.main()
    output = capsys.readouterr().out
    assert called["orchestrated"] is True
    assert "deprecated alias for orchestrated" in output


def test_main_warns_when_target_tests_default_is_used_in_orchestrated_mode(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["prog", "--mode", "orchestrated", "--project-dir", "./tmp-project", "--dry-run"])

    async def fake_run_orchestrated(*args, **kwargs):
        return None

    monkeypatch.setattr(cli, "_run_orchestrated", fake_run_orchestrated)
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
    monkeypatch.setattr(cli, "_run_orchestrated", lambda *args, **kwargs: None)
    cli.main()
    output = capsys.readouterr().out
    assert "Claude CLI credentials were not detected" in output


def test_main_rejects_project_dir_traversal(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["prog", "--project-dir", "../escape", "--dry-run"])

    cli.main()

    output = capsys.readouterr().out
    assert "must stay within generations" in output


def test_readme_documents_official_modes_without_v2() -> None:
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
    assert "--mode {legacy,orchestrated}" in readme
    assert "--mode v2" not in readme
