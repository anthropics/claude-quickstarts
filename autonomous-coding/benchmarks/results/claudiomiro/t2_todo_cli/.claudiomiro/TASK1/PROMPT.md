## PROMPT
Implement the complete CLI application `src/todo_cli/cli.py` with four commands (add, list, complete, delete) using Click framework and JSON storage for data persistence. Handle all edge cases with appropriate error messages and exit codes.

## COMPLEXITY
Medium

## CONTEXT REFERENCE
**For complete environment context, read:**
- `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t2_todo_cli/.claudiomiro/AI_PROMPT.md` - Contains full tech stack, CLI patterns, data structure, acceptance criteria, and constraints

**You MUST read AI_PROMPT.md before executing this task to understand the environment.**

## TASK-SPECIFIC CONTEXT

### Files This Task Will Create
- `src/todo_cli/cli.py` - Main CLI implementation (~80-120 lines)

### Patterns to Follow
- Click CLI group pattern: AI_PROMPT.md:65-82
- JSON storage pattern (load_todos, save_todos): AI_PROMPT.md:85-98
- Todo data structure: AI_PROMPT.md:101-109
  ```python
  {
      "id": 1,
      "description": "Buy groceries",
      "completed": False,
      "created_at": "2024-01-15T10:30:00"
  }
  ```

### Integration Points
- Entry point in pyproject.toml points to `todo_cli.cli:cli`
- `todos.json` is created in working directory at runtime
- TASK2 tests will import from `todo_cli.cli import cli`

## EXTRA DOCUMENTATION

### Command Specifications

**`add <description>`**
- Argument: description (string)
- Validation: reject empty description with error, exit 1
- ID logic: max(existing_ids) + 1, or 1 if empty
- Output: "Added todo: {description}"

**`list`**
- No arguments
- Format: `{id}. [x] {description}` or `{id}. [ ] {description}`
- Empty list: "No todos yet"

**`complete <id>`**
- Argument: id (integer)
- Find todo by ID, set `completed: true`
- Not found: "Todo not found", exit 1
- Success: "Completed todo: {description}"

**`delete <id>`**
- Argument: id (integer)
- Remove todo from list
- Not found: "Todo not found", exit 1
- Success: "Deleted todo: {description}"

### Code Template
```python
import click
import json
import sys
from pathlib import Path
from datetime import datetime

DATA_FILE = Path("todos.json")

def load_todos() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    return json.loads(DATA_FILE.read_text())

def save_todos(todos: list[dict]) -> None:
    DATA_FILE.write_text(json.dumps(todos, indent=2))

@click.group()
def cli():
    """Todo CLI - Manage your tasks from the command line."""
    pass

@cli.command()
@click.argument('description')
def add(description: str) -> None:
    """Add a new todo item."""
    # Implement: validation, ID generation, save, output

@cli.command('list')
def list_todos() -> None:
    """List all todo items."""
    # Implement: load, format output, handle empty

@cli.command()
@click.argument('id', type=int)
def complete(id: int) -> None:
    """Mark a todo as completed."""
    # Implement: find by ID, update, save, handle not found

@cli.command()
@click.argument('id', type=int)
def delete(id: int) -> None:
    """Delete a todo item."""
    # Implement: find by ID, remove, save, handle not found

if __name__ == '__main__':
    cli()
```

## LAYER
1

## PARALLELIZATION
Parallel with: None

## CONSTRAINTS
- IMPORTANT: Do not perform any git commit or git push.
- Use Click for CLI (NOT argparse or typer)
- Use `click.echo()` for output (NOT print)
- Use `sys.exit(1)` for errors
- Store todos.json in current working directory (use `Path("todos.json")`)
- Use ISO 8601 format: `datetime.now().isoformat()`
- Do NOT over-engineer: no classes, no config system, no logging framework
- Do NOT add features not in spec (no due dates, priorities, tags)

## VALIDATION
After completion, verify manually:
```bash
uv run todo add "Test task"          # Should show "Added todo: Test task"
uv run todo list                      # Should show "1. [ ] Test task"
uv run todo complete 1                # Should show "Completed todo: Test task"
uv run todo list                      # Should show "1. [x] Test task"
uv run todo delete 1                  # Should show "Deleted todo: Test task"
uv run todo list                      # Should show "No todos yet"
uv run todo add ""                    # Should error, exit 1
uv run todo complete 999              # Should show "Todo not found", exit 1
```
