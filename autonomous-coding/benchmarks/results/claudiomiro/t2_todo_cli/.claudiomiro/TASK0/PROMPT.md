## PROMPT
Create the project foundation for a Python CLI todo application. Set up the directory structure, pyproject.toml configuration, and initialize the package with uv.

## COMPLEXITY
Low

## CONTEXT REFERENCE
**For complete environment context, read:**
- `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t2_todo_cli/.claudiomiro/AI_PROMPT.md` - Contains full tech stack, architecture, project structure, coding conventions, and pyproject.toml template

**You MUST read AI_PROMPT.md before executing this task to understand the environment.**

## TASK-SPECIFIC CONTEXT

### Files This Task Will Create
- `src/todo_cli/__init__.py` - Package init with `__version__ = "0.1.0"`
- `pyproject.toml` - Package configuration (use template from AI_PROMPT.md:204-229)
- `tests/` directory (empty, for TASK2)

### Patterns to Follow
- pyproject.toml template: AI_PROMPT.md:204-229
- Entry point: `todo = "todo_cli.cli:cli"`
- Build backend: hatchling with `packages = ["src/todo_cli"]`

### Integration Points
- TASK1 depends on this: needs pyproject.toml and __init__.py to exist
- TASK2 depends on this: needs tests/ directory and pytest in dev deps

## EXTRA DOCUMENTATION
The pyproject.toml template is provided exactly in AI_PROMPT.md. Use it as-is:
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

## LAYER
0

## PARALLELIZATION
Parallel with: None

## CONSTRAINTS
- IMPORTANT: Do not perform any git commit or git push.
- Use uv exclusively (NOT pip/poetry)
- Run `uv sync` to initialize and install dependencies
- Do NOT create cli.py yet (that's TASK1)
- Do NOT create test_cli.py yet (that's TASK2)
- Follow pyproject.toml template exactly from AI_PROMPT.md

## VALIDATION
After completion, verify:
1. `ls src/todo_cli/` shows `__init__.py`
2. `ls tests/` directory exists
3. `cat pyproject.toml` matches template
4. `uv sync` completes without error
