# AI_PROMPT.md — Todo CLI Application

---

## 1. Purpose

**What:** Build a complete command-line todo application in Python with persistent JSON storage, proper CLI interface using Click, and comprehensive test coverage.

**Why:** This is a foundational productivity tool demonstrating proper CLI design patterns, data persistence, and test-driven development in Python.

**Success Definition:** A working `todo` CLI command that persists todos to JSON, handles all specified commands (`add`, `list`, `complete`, `delete`, `--help`), passes at least 10 tests, and handles edge cases gracefully with appropriate exit codes.

---

## 2. Environment & Codebase Context

### Tech Stack
- **Language:** Python 3.11+
- **CLI Framework:** Click (use `click` package)
- **Testing:** pytest
- **Package Manager:** uv (NOT pip/poetry)
- **Build Config:** pyproject.toml with entry point

### Project Structure (to be created)
```
t2_todo_cli/
├── .claudiomiro/          # Metadata (exists)
│   ├── AI_PROMPT.md       # This file
│   ├── INITIAL_PROMPT.md  # Original requirements
│   └── ...
├── src/
│   └── todo_cli/
│       ├── __init__.py    # Package init (version, exports)
│       └── cli.py         # Main CLI implementation
├── tests/
│   └── test_cli.py        # Test suite (10+ tests)
├── pyproject.toml         # Package config with entry point
└── todos.json             # Data file (created at runtime)
```

### Working Directory
`/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t2_todo_cli/`

### Package Manager Commands
```bash
uv add click              # Add Click dependency
uv add pytest --dev       # Add pytest as dev dependency
uv sync                   # Sync dependencies
uv run pytest             # Run tests
uv run todo               # Run CLI after install
```

### Entry Point Configuration
The `pyproject.toml` must define a console script entry point:
```toml
[project.scripts]
todo = "todo_cli.cli:cli"
```

---

## 3. Related Code Context

### Click CLI Pattern Reference
```python
import click

@click.group()
def cli():
    """Todo CLI - Manage your tasks from the command line."""
    pass

@cli.command()
@click.argument('description')
def add(description):
    """Add a new todo item."""
    # Implementation here
    click.echo("Added: ...")

if __name__ == '__main__':
    cli()
```

### JSON Storage Pattern
```python
import json
from pathlib import Path
from datetime import datetime

DATA_FILE = Path("todos.json")

def load_todos() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    return json.loads(DATA_FILE.read_text())

def save_todos(todos: list[dict]) -> None:
    DATA_FILE.write_text(json.dumps(todos, indent=2))
```

### Todo Data Structure
```python
{
    "id": 1,                           # int, auto-incremented
    "description": "Buy groceries",    # str, non-empty
    "completed": False,                # bool
    "created_at": "2024-01-15T10:30:00"  # ISO 8601 timestamp
}
```

---

## 4. Acceptance Criteria

### Core Commands
- [ ] `todo add "task description"` — Creates a new todo with auto-incremented ID, stores in JSON
- [ ] `todo list` — Displays all todos with `[x]` for completed, `[ ]` for pending, numbered by ID
- [ ] `todo complete <id>` — Marks specified todo as completed (sets `completed: true`)
- [ ] `todo delete <id>` — Removes specified todo from storage
- [ ] `todo --help` — Shows usage information (Click provides this automatically)

### Data Persistence
- [ ] Todos stored in `todos.json` in working directory
- [ ] Each todo contains: `id` (int), `description` (str), `completed` (bool), `created_at` (ISO timestamp)
- [ ] IDs auto-increment (next ID = max existing ID + 1, or 1 if empty)
- [ ] Data persists between program runs

### Output Format
- [ ] `list` output format: `1. [x] Completed task` or `2. [ ] Pending task`
- [ ] Success messages: "Added todo: ...", "Completed todo: ...", "Deleted todo: ..."
- [ ] Exit code 0 for successful operations
- [ ] Exit code 1 for errors

### Edge Case Handling
- [ ] Empty description on `add` → Error message, exit code 1
- [ ] Invalid/non-existent ID on `complete` → "Todo not found", exit code 1
- [ ] Invalid/non-existent ID on `delete` → "Todo not found", exit code 1
- [ ] Empty todo list on `list` → "No todos yet"

### Testing Requirements
- [ ] At least 10 tests in `tests/test_cli.py`
- [ ] Tests cover all commands (add, list, complete, delete)
- [ ] Tests cover edge cases (empty description, invalid ID, empty list)
- [ ] Tests use Click's CliRunner for CLI testing
- [ ] Tests use temporary files/directories for isolation

### Code Quality
- [ ] Code passes linting (ruff check)
- [ ] Proper type hints on functions
- [ ] Clean, readable code following PEP 8

---

## 5. Implementation Guidance

### Execution Layers

**Layer 0 — Foundation:**
1. Create project structure (`src/todo_cli/`, `tests/`)
2. Create `pyproject.toml` with dependencies and entry point
3. Create `src/todo_cli/__init__.py`
4. Initialize uv project and sync dependencies

**Layer 1 — Core Implementation:**
1. Implement `cli.py` with Click commands
2. Implement JSON storage functions (load/save)
3. Implement each command: add, list, complete, delete

**Layer 2 — Testing:**
1. Create `test_cli.py` with CliRunner tests
2. Write tests for happy paths
3. Write tests for edge cases

**Layer 3 — Validation:**
1. Run all tests
2. Run linter
3. Manual verification of CLI commands

### Expected Artifacts

| File | Purpose |
|------|---------|
| `pyproject.toml` | Package config, dependencies, entry point |
| `src/todo_cli/__init__.py` | Package init with version |
| `src/todo_cli/cli.py` | Main CLI implementation |
| `tests/test_cli.py` | Test suite with 10+ tests |

### Constraints

**DO:**
- Use Click for CLI (not argparse or typer)
- Use `click.echo()` for output (not print)
- Use `sys.exit(1)` or `raise SystemExit(1)` for errors
- Store todos.json in current working directory
- Use ISO 8601 format for timestamps (`datetime.now().isoformat()`)

**DO NOT:**
- Use pip/poetry (use uv only)
- Create extra files beyond requirements
- Over-engineer with classes if functions suffice
- Add features not specified (no due dates, priorities, etc.)

### pyproject.toml Template
```toml
[project]
name = "todo-cli"
version = "0.1.0"
description = "A simple command-line todo application"
requires-python = ">=3.11"
dependencies = [
    "click>=8.0",
]

[project.scripts]
todo = "todo_cli.cli:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/todo_cli"]

[dependency-groups]
dev = [
    "pytest>=7.0",
    "ruff>=0.1",
]
```

---

## 5.1 Testing Guidance

### Test Categories Required

**Happy Path Tests (minimum 4):**
1. `test_add_todo` — Add a todo successfully, verify it exists
2. `test_list_todos` — List todos shows correct format
3. `test_complete_todo` — Mark todo complete, verify status change
4. `test_delete_todo` — Delete todo, verify removal

**Edge Case Tests (minimum 4):**
5. `test_add_empty_description` — Empty description shows error
6. `test_complete_invalid_id` — Invalid ID shows "Todo not found"
7. `test_delete_invalid_id` — Invalid ID shows "Todo not found"
8. `test_list_empty` — Empty list shows "No todos yet"

**Integration Tests (minimum 2):**
9. `test_persistence` — Data persists across CLI invocations
10. `test_complete_workflow` — Add → Complete → List shows [x]

### Test Pattern with Click
```python
from click.testing import CliRunner
from todo_cli.cli import cli
import tempfile
import os

def test_add_todo():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['add', 'Buy groceries'])
        assert result.exit_code == 0
        assert 'Added' in result.output
```

### Test Isolation
- Use `runner.isolated_filesystem()` for file isolation
- OR use `tmp_path` fixture with environment variable to override data file location
- Each test must be independent

---

## 6. Verification and Traceability

### Self-Verification Checklist

Before marking complete, verify:

**Commands:**
- [ ] `uv run todo add "Test task"` → Adds task, shows confirmation
- [ ] `uv run todo list` → Shows task with `[ ]` status
- [ ] `uv run todo complete 1` → Shows completion message
- [ ] `uv run todo list` → Shows task with `[x]` status
- [ ] `uv run todo delete 1` → Shows deletion message
- [ ] `uv run todo list` → Shows "No todos yet"

**Edge Cases:**
- [ ] `uv run todo add ""` → Error message, exit 1
- [ ] `uv run todo complete 999` → "Todo not found", exit 1
- [ ] `uv run todo delete 999` → "Todo not found", exit 1

**Tests:**
- [ ] `uv run pytest` → All tests pass
- [ ] Test count >= 10

**Linting:**
- [ ] `uv run ruff check src/ tests/` → No errors

### Traceability Matrix

| Requirement | Implementation | Test |
|-------------|----------------|------|
| add command | cli.py:add() | test_add_todo |
| list command | cli.py:list() | test_list_todos |
| complete command | cli.py:complete() | test_complete_todo |
| delete command | cli.py:delete() | test_delete_todo |
| --help | Click automatic | N/A |
| JSON storage | load_todos/save_todos | test_persistence |
| Empty description error | add() validation | test_add_empty_description |
| Invalid ID error | complete()/delete() | test_complete_invalid_id, test_delete_invalid_id |
| Empty list message | list() | test_list_empty |

---

## 7. Reasoning Boundaries

### Follow These Patterns
- Use Click decorators consistently (`@cli.command()`, `@click.argument()`)
- Keep data functions pure (load_todos returns list, save_todos takes list)
- Exit codes: 0 = success, 1 = error

### Do Not Over-Engineer
- No database abstraction layer — direct JSON file operations are fine
- No configuration system — hardcode `todos.json` filename
- No logging framework — use `click.echo()`
- No todo class — dict is sufficient for this scope

### When Uncertain
- Check Click documentation for CLI patterns
- Follow existing Python conventions (PEP 8)
- Ask rather than assume for ambiguous requirements

---

## Summary

Build a Python CLI todo app using Click with JSON persistence. Four commands (add, list, complete, delete) plus help. Store todos in `todos.json` with id/description/completed/created_at fields. Handle errors gracefully with exit code 1. Write 10+ pytest tests covering happy paths and edge cases. Use uv for package management.
