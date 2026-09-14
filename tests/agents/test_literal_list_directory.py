import asyncio

from tools.file_tools import FileReadTool


def test_directory_with_glob_characters(tmp_path):
    directory = tmp_path / "[data]"
    directory.mkdir()
    (directory / "wanted.txt").touch()
    (directory / "other.csv").touch()
    result = asyncio.run(
        FileReadTool().execute("list", str(directory), pattern="*.txt")
    )
    assert result == "📄 wanted.txt"


def test_nested_pattern_preserves_relative_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    directory = tmp_path / "data" / "sub" / "data"
    directory.mkdir(parents=True)
    (directory / "file.txt").touch()
    result = asyncio.run(
        FileReadTool().execute("list", "data", pattern="sub/data/*.txt")
    )
    assert result == "📄 sub/data/file.txt"
