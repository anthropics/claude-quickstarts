import asyncio

from tools.file_tools import FileWriteTool


def test_write_empty_content(tmp_path):
    path = tmp_path / "empty.txt"
    tool = FileWriteTool()
    for existing in [False, True]:
        if existing:
            path.write_text("old contents")
        result = asyncio.run(tool.execute("write", str(path), content=""))
        assert not result.startswith("Error")
        assert path.read_text() == ""


def test_edit_can_delete_text(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text("remove this keep")
    result = asyncio.run(
        FileWriteTool().execute("edit", str(path), old_text="remove this ", new_text="")
    )
    assert not result.startswith("Error")
    assert path.read_text() == "keep"


def test_missing_arguments_do_not_modify_files(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text("keep")
    tool = FileWriteTool()
    for args in [
        {"operation": "write"},
        {"operation": "edit", "old_text": "keep"},
        {"operation": "edit", "old_text": "", "new_text": "other"},
    ]:
        assert asyncio.run(tool.execute(path=str(path), **args)).startswith("Error")
        assert path.read_text() == "keep"
