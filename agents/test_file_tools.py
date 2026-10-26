"""File writes distinguish omitted arguments from valid empty strings."""

import asyncio
from pathlib import Path

import pytest

from agents.tools.file_tools import FileWriteTool


@pytest.mark.parametrize("existing", [False, True])
def test_write_empty_content(tmp_path: Path, existing: bool) -> None:
    path = tmp_path / "nested" / "empty.txt"
    if existing:
        path.parent.mkdir()
        path.write_text("previous content", encoding="utf-8")

    result = asyncio.run(FileWriteTool().execute("write", str(path), content=""))

    assert result.startswith("Successfully wrote 0 characters")
    assert path.read_bytes() == b""


@pytest.mark.parametrize(
    ("original", "old_text", "expected", "prefix"),
    [
        ("keep obsolete text", "obsolete ", "keep text", "Successfully edited"),
        ("remove", "remove", "", "Successfully edited"),
        ("a,b,a", "a", ",b,", "Warning: Found 2 occurrences"),
        ("保留删除内容", "删除", "保留内容", "Successfully edited"),
    ],
)
def test_edit_deletes_matching_text(
    tmp_path: Path, original: str, old_text: str, expected: str, prefix: str
) -> None:
    path = tmp_path / "notes.txt"
    path.write_text(original, encoding="utf-8")

    result = asyncio.run(
        FileWriteTool().execute("edit", str(path), old_text=old_text, new_text="")
    )

    assert result.startswith(prefix)
    assert path.read_text(encoding="utf-8") == expected


@pytest.mark.parametrize("arguments", [{}, {"content": None}])
@pytest.mark.parametrize("existing", [False, True])
def test_write_without_content_does_not_change_files(
    tmp_path: Path, arguments: dict[str, str | None], existing: bool
) -> None:
    path = tmp_path / "notes.txt"
    if existing:
        path.write_text("keep me", encoding="utf-8")

    result = asyncio.run(FileWriteTool().execute("write", str(path), **arguments))

    assert result == "Error: content parameter is required"
    assert path.exists() is existing
    if existing:
        assert path.read_text(encoding="utf-8") == "keep me"


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"old_text": "keep"},
        {"old_text": "keep", "new_text": None},
        {"new_text": "replacement"},
        {"old_text": None, "new_text": "replacement"},
        {"old_text": "", "new_text": "replacement"},
        {"old_text": "", "new_text": ""},
    ],
)
def test_edit_requires_search_text_and_a_replacement(
    tmp_path: Path, arguments: dict[str, str | None]
) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("keep me", encoding="utf-8")

    result = asyncio.run(FileWriteTool().execute("edit", str(path), **arguments))

    assert result.startswith("Error: both old_text and new_text parameters")
    assert path.read_text(encoding="utf-8") == "keep me"


def test_nonempty_write_and_replacement(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "notes.txt"
    tool = FileWriteTool()

    written = asyncio.run(tool.execute("write", str(path), content="before"))
    edited = asyncio.run(
        tool.execute("edit", str(path), old_text="before", new_text="after")
    )

    assert written.startswith("Successfully wrote")
    assert edited.startswith("Successfully edited")
    assert path.read_text(encoding="utf-8") == "after"


def test_deleting_an_absent_match_leaves_file_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("keep me", encoding="utf-8")

    result = asyncio.run(
        FileWriteTool().execute("edit", str(path), old_text="absent", new_text="")
    )

    assert result.startswith("Error: The specified text was not found")
    assert path.read_text(encoding="utf-8") == "keep me"


def test_deleting_from_a_missing_file_does_not_create_it(tmp_path: Path) -> None:
    path = tmp_path / "missing.txt"

    result = asyncio.run(
        FileWriteTool().execute("edit", str(path), old_text="absent", new_text="")
    )

    assert result.startswith("Error: File not found")
    assert not path.exists()
