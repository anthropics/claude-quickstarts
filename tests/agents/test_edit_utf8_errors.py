import asyncio

from tools.file_tools import FileReadTool, FileWriteTool


def test_edit_rejects_invalid_utf8_without_modifying_file(tmp_path):
    path = tmp_path / "data.bin"
    original = b"replace me\xff tail"
    path.write_bytes(original)
    result = asyncio.run(
        FileWriteTool().execute(
            "edit", str(path), old_text="replace me", new_text="changed"
        )
    )
    assert result.startswith("Error")
    assert path.read_bytes() == original


def test_edit_preserves_valid_unicode(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text("café replace 世界", encoding="utf-8")
    result = asyncio.run(
        FileWriteTool().execute(
            "edit", str(path), old_text="replace", new_text="changed"
        )
    )
    assert not result.startswith("Error")
    assert path.read_text(encoding="utf-8") == "café changed 世界"


def test_read_only_preview_still_replaces_invalid_bytes(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_bytes(b"hello\xff")
    result = asyncio.run(FileReadTool().execute("read", str(path)))
    assert result == "hello\ufffd"
