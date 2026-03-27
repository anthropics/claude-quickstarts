"""Prompt loading utilities for V1 and V2 harness flows."""

from __future__ import annotations

import shutil
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt_file(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text()


def get_initializer_prompt(target_test_count: int = 200) -> str:
    prompt = load_prompt_file("initializer_prompt.md")
    return prompt.replace("{{TARGET_TEST_COUNT}}", str(target_test_count))


def get_coding_prompt() -> str:
    return load_prompt_file("coding_prompt.md")


def get_planner_prompt() -> str:
    return load_prompt_file("planner_prompt.md")


def get_builder_prompt() -> str:
    return load_prompt_file("builder_prompt.md")


def get_evaluator_prompt() -> str:
    return load_prompt_file("evaluator_prompt.md")


def copy_spec_to_project(project_dir: Path) -> None:
    spec_source = PROMPTS_DIR / "app_spec.txt"
    spec_dest = project_dir / "app_spec.txt"
    if not spec_dest.exists():
        shutil.copy(spec_source, spec_dest)
        print("Copied app_spec.txt to project directory")
