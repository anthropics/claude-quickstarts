#!/usr/bin/env python3
"""Validate registry.yaml against the actual quickstart directories.

Checks:
  - registry.yaml exists and is valid YAML
  - Every entry has required fields: name, path, description, categories,
    language, difficulty, requires
  - Every path listed in the registry points to an existing directory
  - No quickstart directory (non-hidden, non-special) is missing from the
    registry
  - difficulty is one of: beginner, intermediate, advanced

Usage:
    python3 scripts/validate-registry.py
"""

import os
import sys
import yaml

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(REPO_ROOT, "registry.yaml")

REQUIRED_FIELDS = {"name", "path", "description", "categories", "language",
                   "difficulty", "requires"}
VALID_DIFFICULTIES = {"beginner", "intermediate", "advanced"}

# Top-level names that are never quickstart directories
EXCLUDED_NAMES = {"scripts", ".git", ".github", "__pycache__"}


def fail(message: str) -> None:
    print(f"  FAIL  {message}", file=sys.stderr)


def ok(message: str) -> None:
    print(f"  OK    {message}")


def warn(message: str) -> None:
    print(f"  WARN  {message}")


def section(title: str) -> None:
    print(f"\n[{title}]")


# ---------------------------------------------------------------------------
# Check 1 – registry.yaml exists and parses
# ---------------------------------------------------------------------------

def load_registry() -> dict:
    section("Loading registry.yaml")
    if not os.path.isfile(REGISTRY_PATH):
        fail(f"registry.yaml not found at {REGISTRY_PATH}")
        sys.exit(1)

    with open(REGISTRY_PATH, "r") as fh:
        try:
            data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            fail(f"YAML parse error: {exc}")
            sys.exit(1)

    if not isinstance(data, dict):
        fail("registry.yaml must be a YAML mapping at the top level")
        sys.exit(1)

    if "quickstarts" not in data or not isinstance(data["quickstarts"], list):
        fail("registry.yaml must contain a 'quickstarts' list")
        sys.exit(1)

    ok(f"Loaded {len(data['quickstarts'])} quickstart entries")
    return data


# ---------------------------------------------------------------------------
# Check 2 – required fields and valid values
# ---------------------------------------------------------------------------

def validate_fields(quickstarts: list) -> list[str]:
    section("Validating entry fields")
    errors: list[str] = []

    for entry in quickstarts:
        name = entry.get("name", "<unnamed>")
        missing = REQUIRED_FIELDS - set(entry.keys())
        if missing:
            msg = f"'{name}' is missing fields: {sorted(missing)}"
            fail(msg)
            errors.append(msg)
        else:
            ok(f"'{name}' has all required fields")

        difficulty = entry.get("difficulty", "")
        if difficulty not in VALID_DIFFICULTIES:
            msg = (f"'{name}' has invalid difficulty '{difficulty}'. "
                   f"Must be one of: {sorted(VALID_DIFFICULTIES)}")
            fail(msg)
            errors.append(msg)

        for list_field in ("categories", "requires"):
            value = entry.get(list_field)
            if value is not None and not isinstance(value, list):
                msg = f"'{name}' field '{list_field}' must be a list"
                fail(msg)
                errors.append(msg)
            elif isinstance(value, list):
                if len(value) == 0:
                    errors.append(f"Quickstart '{name}': '{list_field}' must not be empty")

    return errors


# ---------------------------------------------------------------------------
# Check 3 – every registered path exists on disk
# ---------------------------------------------------------------------------

def validate_paths(quickstarts: list) -> list[str]:
    section("Checking registered paths exist on disk")
    errors: list[str] = []

    for entry in quickstarts:
        name = entry.get("name", "<unnamed>")
        path = entry.get("path", "")
        full_path = os.path.join(REPO_ROOT, path)
        if os.path.isdir(full_path):
            ok(f"'{name}' -> {path}/")
            readme_path = os.path.join(full_path, "README.md")
            if not os.path.isfile(readme_path):
                warn(f"Quickstart '{name}': missing README.md in {entry['path']}")
        else:
            msg = f"'{name}' path '{path}' does not exist at {full_path}"
            fail(msg)
            errors.append(msg)

    return errors


# ---------------------------------------------------------------------------
# Check 4 – no quickstart directory is missing from the registry
# ---------------------------------------------------------------------------

def validate_completeness(quickstarts: list) -> list[str]:
    section("Checking all quickstart directories are registered")
    errors: list[str] = []

    registered_paths = {entry.get("path") for entry in quickstarts}

    for item in sorted(os.listdir(REPO_ROOT)):
        if item.startswith(".") or item in EXCLUDED_NAMES:
            continue
        full_path = os.path.join(REPO_ROOT, item)
        if not os.path.isdir(full_path):
            continue
        if item in registered_paths:
            ok(f"'{item}' is registered")
        else:
            msg = f"Directory '{item}' exists but is not listed in registry.yaml"
            fail(msg)
            errors.append(msg)

    return errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("registry.yaml validator")
    print("=" * 60)

    data = load_registry()
    quickstarts = data["quickstarts"]

    errors: list[str] = []
    errors += validate_fields(quickstarts)
    errors += validate_paths(quickstarts)
    errors += validate_completeness(quickstarts)

    print("\n" + "=" * 60)
    if errors:
        print(f"FAILED – {len(errors)} error(s) found:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print(f"PASSED – registry.yaml is valid "
              f"({len(quickstarts)} quickstarts registered)")


if __name__ == "__main__":
    main()
