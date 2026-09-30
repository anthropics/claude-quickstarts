"""Prompt and progress files use UTF-8 independently of the system locale."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("utf8_mode", ["0", "1"])
def test_non_ascii_prompt_and_progress(tmp_path: Path, utf8_mode: str) -> None:
    text = "Zażółć gęślą jaźń"
    (tmp_path / "example.md").write_text(text, encoding="utf-8")
    (tmp_path / "feature_list.json").write_text(
        json.dumps([{"description": text, "passes": True}], ensure_ascii=False),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from pathlib import Path; "
            "import prompts; from progress import count_passing_tests; "
            "root = Path(sys.argv[1]); prompts.PROMPTS_DIR = root; "
            "assert prompts.load_prompt('example') == " + ascii(text) + "; "
            "assert count_passing_tests(root) == (1, 1)",
            str(tmp_path),
        ],
        cwd=Path(__file__).parent,
        env={
            **os.environ,
            "LC_ALL": "C",
            "PYTHONUTF8": utf8_mode,
            "PYTHONCOERCECLOCALE": "0",
        },
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
