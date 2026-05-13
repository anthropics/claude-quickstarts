import tempfile
from pathlib import Path

import pytest
from PIL import Image

from computer_use.tools.editor import EditorTool


@pytest.fixture
def tool(tmp_path: Path) -> EditorTool:
    return EditorTool(tmp_path)


def test_create_and_view_roundtrip(tool: EditorTool) -> None:
    tool.execute(command="create", path="notes.md", file_text="hello\nworld\n")
    res = tool.execute(command="view", path="notes.md")
    assert res.output is not None
    assert "1\thello" in res.output
    assert "2\tworld" in res.output


def test_view_range(tool: EditorTool) -> None:
    tool.execute(
        command="create", path="x.txt", file_text="\n".join(f"line{i}" for i in range(1, 11))
    )
    res = tool.execute(command="view", path="x.txt", view_range=[3, 5])
    assert res.output is not None
    assert "line3" in res.output
    assert "line5" in res.output
    assert "line1\n" not in res.output
    assert "line6" not in res.output


def test_str_replace_unique(tool: EditorTool) -> None:
    tool.execute(command="create", path="a.txt", file_text="foo bar foo")
    err = tool.execute(command="str_replace", path="a.txt", old_str="foo", new_str="baz")
    assert err.is_error and "matched 2 times" in (err.error or "")

    tool.execute(command="create", path="a.txt", file_text="foo bar")
    ok = tool.execute(command="str_replace", path="a.txt", old_str="foo", new_str="baz")
    assert not ok.is_error
    out = tool.execute(command="view", path="a.txt")
    assert out.output is not None
    assert "baz bar" in out.output


def test_insert(tool: EditorTool) -> None:
    tool.execute(command="create", path="a.txt", file_text="a\nc\n")
    tool.execute(command="insert", path="a.txt", insert_line=1, new_str="b")
    res = tool.execute(command="view", path="a.txt")
    assert res.output is not None
    assert "1\ta" in res.output
    assert "2\tb" in res.output
    assert "3\tc" in res.output


def test_path_escape_rejected(tool: EditorTool) -> None:
    res = tool.execute(command="view", path="../etc/passwd")
    assert res.is_error and "escapes" in (res.error or "")
    res = tool.execute(command="create", path="/tmp/abs.txt", file_text="x")
    assert res.is_error and "escapes" in (res.error or "")


def test_view_directory(tool: EditorTool) -> None:
    tool.execute(command="create", path="sub/one.txt", file_text="x")
    tool.execute(command="create", path="sub/two.txt", file_text="y")
    res = tool.execute(command="view", path="sub")
    assert res.output is not None
    assert "one.txt" in res.output
    assert "two.txt" in res.output


def test_view_image_returns_image_block(tool: EditorTool, tmp_path: Path) -> None:
    img = Image.new("RGB", (200, 150), (10, 200, 30))
    img.save(tmp_path / "pic.png")
    res = tool.execute(command="view", path="pic.png")
    assert not res.is_error
    assert res.base64_image is not None
    assert "200x150" in (res.output or "")
    blocks = res.to_api_content()
    assert any(b.get("type") == "image" for b in blocks)


def test_view_small_image_ok(tool: EditorTool, tmp_path: Path) -> None:
    """Small/solid images are legitimate file content, not failed screenshots."""
    Image.new("RGB", (40, 30), (255, 0, 0)).save(tmp_path / "icon.png")
    res = tool.execute(command="view", path="icon.png")
    assert not res.is_error
    assert res.base64_image is not None


def test_view_pdf_returns_document_block(tool: EditorTool, tmp_path: Path) -> None:
    # A minimal valid one-page PDF.
    minimal_pdf = (
        b"%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 100 100]>>endobj "
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000052 00000 n \n0000000100 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n164\n%%EOF"
    )
    (tmp_path / "doc.pdf").write_bytes(minimal_pdf)
    res = tool.execute(command="view", path="doc.pdf")
    assert not res.is_error
    assert res.base64_pdf is not None
    blocks = res.to_api_content()
    assert any(b.get("type") == "document" for b in blocks)


def test_shell_shares_scratch_dir() -> None:
    """Bash and the editor see the same persistent directory."""
    from computer_use.tools.shell import BashTool

    with tempfile.TemporaryDirectory() as d:
        scratch = Path(d).resolve()
        editor = EditorTool(scratch)
        bash = BashTool(scratch)
        editor.execute(command="create", path="hello.txt", file_text="hi\n")
        res = bash.execute(command="cat hello.txt")
        assert (res.output or "").strip() == "hi"
        bash.execute(command="echo written-by-bash > frombash.txt")
        view = editor.execute(command="view", path="frombash.txt")
        assert view.output is not None
        assert "written-by-bash" in view.output
