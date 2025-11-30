@dependencies []
# Task: Project Foundation and Scaffolding

## Summary
Create the complete project structure, initialize the Python package with uv, and set up all configuration files. This is the foundation task that must complete before any implementation can begin.

## Context Reference
**For complete environment context, see:**
- `../AI_PROMPT.md` - Contains full tech stack (Python 3.11+, Click, pytest, uv), architecture, coding conventions, and pyproject.toml template

**Task-Specific Context:**
- Files to create:
  - `pyproject.toml` - Package configuration with entry point (template in AI_PROMPT.md:204-229)
  - `src/todo_cli/__init__.py` - Package init with version string
- Directories to create:
  - `src/todo_cli/` - Main package directory
  - `tests/` - Test directory
- Commands to run:
  - `uv sync` - Initialize project and install dependencies

## Complexity
Low

## Dependencies
Depends on: None
Blocks: TASK1, TASK2, TASKΩ
Parallel with: None

## Detailed Steps
1. Create directory structure: `src/todo_cli/` and `tests/`
2. Create `pyproject.toml` using the template from AI_PROMPT.md section 5
3. Create `src/todo_cli/__init__.py` with version `__version__ = "0.1.0"`
4. Run `uv sync` to initialize the project and install dependencies

## Acceptance Criteria
- [ ] Directory structure exists: `src/todo_cli/`, `tests/`
- [ ] `pyproject.toml` exists with correct dependencies (click>=8.0) and entry point (`todo = "todo_cli.cli:cli"`)
- [ ] `src/todo_cli/__init__.py` exists with `__version__` defined
- [ ] `uv sync` completes successfully
- [ ] Dev dependencies include pytest and ruff

## Code Review Checklist
- [ ] pyproject.toml follows template from AI_PROMPT.md
- [ ] Entry point correctly points to `todo_cli.cli:cli`
- [ ] Using hatchling as build backend
- [ ] Requires-python set to >=3.11

## Reasoning Trace
This is a straightforward foundation task. The pyproject.toml template is provided in AI_PROMPT.md, so we follow it exactly. Using uv for package management as specified. The __init__.py is minimal as over-engineering is discouraged.
