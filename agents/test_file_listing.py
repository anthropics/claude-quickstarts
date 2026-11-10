"""Regression coverage for literal directory names in the file-list tool."""

import asyncio
import os
from pathlib import Path

import pytest

from agents.tools.file_tools import FileReadTool


@pytest.mark.parametrize(
    "name",
    [
        "reports[2026]",
        pytest.param(
            "report?",
            marks=pytest.mark.skipif(
                os.name == "nt", reason="Invalid Windows filename"
            ),
        ),
        pytest.param(
            "report*",
            marks=pytest.mark.skipif(
                os.name == "nt", reason="Invalid Windows filename"
            ),
        ),
    ],
)
def test_list_directory_with_glob_characters(tmp_path: Path, name: str) -> None:
    directory = tmp_path / name
    directory.mkdir()
    (directory / "notes.txt").write_text("notes", encoding="utf-8")
    (directory / "data.csv").write_text("data", encoding="utf-8")
    decoy = tmp_path / ("reports2" if "[" in name else "reportx")
    decoy.mkdir()
    (decoy / "wrong.txt").write_text("wrong", encoding="utf-8")

    result = asyncio.run(
        FileReadTool().execute("list", str(directory), pattern="*.txt")
    )

    assert result == "📄 notes.txt"


def test_list_preserves_nested_relative_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    directory = Path("reports")
    nested = directory / "child" / "reports"
    nested.mkdir(parents=True)
    (nested / "notes.txt").write_text("notes", encoding="utf-8")

    result = asyncio.run(
        FileReadTool().execute("list", str(directory), pattern="*/*/*.txt")
    )

    assert result == "📄 child/reports/notes.txt"
