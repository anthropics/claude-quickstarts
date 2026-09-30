import csv
from pathlib import Path

import pytest

from computer_use_demo.tools.base import ToolError
from computer_use_demo.tools.edit import EditTool20250728


@pytest.fixture
def edit_tool() -> EditTool20250728:
    return EditTool20250728()


@pytest.mark.parametrize("command", ["str_replace", "insert"])
async def test_edit_preserves_unmodified_makefile_recipe(
    edit_tool: EditTool20250728, tmp_path: Path, command: str
) -> None:
    path = tmp_path / "Makefile"
    original = '# old description\nall:\n\t@printf "ok\\n"\n'
    path.write_text(original)

    if command == "str_replace":
        result = await edit_tool(
            command="str_replace",
            path=str(path),
            old_str="old description",
            new_str="new description",
        )
        expected = original.replace("old description", "new description")
    else:
        result = await edit_tool(
            command="insert", path=str(path), insert_line=0, insert_text="# heading"
        )
        expected = "# heading\n" + original

    assert path.read_text() == expected
    assert result.output and '\t@printf "ok\\n"' in result.output
    assert edit_tool._file_history[path] == [original]


async def test_replacement_preserves_tsv_columns(
    edit_tool: EditTool20250728, tmp_path: Path
) -> None:
    path = tmp_path / "data.tsv"
    path.write_text("kind\tvalue\nx\told\ny\tkeep\n")

    await edit_tool(command="str_replace", path=str(path), old_str="old", new_str="new")

    with path.open(newline="") as handle:
        assert list(csv.reader(handle, delimiter="\t")) == [
            ["kind", "value"],
            ["x", "new"],
            ["y", "keep"],
        ]


async def test_replacement_distinguishes_tabs_from_spaces(
    edit_tool: EditTool20250728, tmp_path: Path
) -> None:
    path = tmp_path / "mixed.txt"
    path.write_text("key\told\nkey     old\n")

    await edit_tool(
        command="str_replace",
        path=str(path),
        old_str="key\told",
        new_str="key\tnew",
    )

    assert path.read_text() == "key\tnew\nkey     old\n"


@pytest.mark.parametrize(
    ("content", "old_str"),
    [("key\tvalue\n", "key     value"), ("key     value\n", "key\tvalue")],
)
async def test_replacement_requires_verbatim_whitespace(
    edit_tool: EditTool20250728, tmp_path: Path, content: str, old_str: str
) -> None:
    path = tmp_path / "literal.txt"
    path.write_text(content)

    with pytest.raises(ToolError, match="did not appear verbatim"):
        await edit_tool(
            command="str_replace", path=str(path), old_str=old_str, new_str="new"
        )

    assert path.read_text() == content
    assert not edit_tool._file_history[path]


async def test_insert_preserves_new_recipe_tab(
    edit_tool: EditTool20250728, tmp_path: Path
) -> None:
    path = tmp_path / "Makefile"
    path.write_text("all:\n")

    result = await edit_tool(
        command="insert",
        path=str(path),
        insert_line=1,
        insert_text='\t@printf "ok\\n"',
    )

    assert path.read_text() == 'all:\n\t@printf "ok\\n"\n'
    assert result.output and '\t@printf "ok\\n"' in result.output


@pytest.mark.parametrize("view_range", [None, [2, 2]])
async def test_view_content_can_be_used_for_verbatim_replacement(
    edit_tool: EditTool20250728, tmp_path: Path, view_range: list[int] | None
) -> None:
    path = tmp_path / "Makefile"
    original = 'all:\n\t@printf "old\\n"\n'
    path.write_text(original)

    view = await edit_tool(command="view", path=str(path), view_range=view_range)
    assert view.output
    recipe = next(
        line.split("\t", 1)[1]
        for line in view.output.splitlines()
        if line.startswith("     2\t")
    )
    assert recipe == '\t@printf "old\\n"'
    assert path.read_text() == original

    await edit_tool(
        command="str_replace",
        path=str(path),
        old_str=recipe,
        new_str=recipe.replace("old", "new"),
    )

    assert path.read_text() == original.replace("old", "new")
