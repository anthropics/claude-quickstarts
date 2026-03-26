"""Utilities for deterministic artifact paths, I/O, and schema validation."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate

SCHEMA_DIR = Path(__file__).parent / "schemas"


class ArtifactPaths:
    """Well-known artifact paths rooted at a project directory."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.planning_dir = project_dir / "planning"
        self.state_dir = project_dir / "state"
        self.qa_dir = project_dir / "qa"
        self.builder_dir = project_dir / "builder"

    def ensure_dirs(self) -> None:
        for directory in [self.planning_dir, self.state_dir, self.qa_dir, self.builder_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    @property
    def run_state(self) -> Path:
        return self.state_dir / "run_state.json"

    @property
    def acceptance_criteria(self) -> Path:
        return self.planning_dir / "acceptance_criteria.json"

    @property
    def work_backlog(self) -> Path:
        return self.planning_dir / "work_backlog.json"

    @property
    def expanded_spec(self) -> Path:
        return self.planning_dir / "expanded_spec.md"

    @property
    def architecture(self) -> Path:
        return self.planning_dir / "architecture.md"

    def sprint_contract_json(self, round_number: int) -> Path:
        return self.planning_dir / f"sprint_contract_round_{round_number:02d}.json"

    def round_state(self, round_number: int) -> Path:
        return self.state_dir / f"round_state_{round_number:02d}.json"

    def qa_report_json(self, round_number: int) -> Path:
        return self.qa_dir / f"qa_report_round_{round_number:02d}.json"

    def qa_report_md(self, round_number: int) -> Path:
        return self.qa_dir / f"qa_report_round_{round_number:02d}.md"

    def build_report_md(self, round_number: int) -> Path:
        return self.builder_dir / f"build_report_round_{round_number:02d}.md"


@lru_cache(maxsize=None)
def _load_schema(name: str) -> dict[str, Any]:
    path = SCHEMA_DIR / f"{name}.schema.json"
    return json.loads(path.read_text())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n")
    tmp.replace(path)


def read_json(
    path: Path,
    default: dict[str, Any] | None = None,
    *,
    context: str = "artifact",
) -> dict[str, Any]:
    fallback = default if default is not None else {}
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        print(
            f"[V3.2] Warning: malformed JSON for {context} at {path}: {exc}. "
            "Using deterministic fallback."
        )
        return fallback


def validate_against_schema(payload: dict[str, Any], schema_name: str) -> None:
    schema = _load_schema(schema_name)
    validate(instance=payload, schema=schema)


def write_validated_json(path: Path, payload: dict[str, Any], schema_name: str) -> None:
    validate_against_schema(payload, schema_name)
    write_json(path, payload)


def safe_validate(payload: dict[str, Any], schema_name: str) -> tuple[bool, str]:
    try:
        validate_against_schema(payload, schema_name)
        return True, ""
    except ValidationError as exc:
        return False, str(exc)
