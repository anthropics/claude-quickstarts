# Research for TASK1

## Context Reference
**For tech stack and conventions, see:**
- `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t2_todo_cli/.claudiomiro/AI_PROMPT.md` - Universal context (Python 3.11+, Click, pytest, uv)
- `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t2_todo_cli/.claudiomiro/TASK1/TASK.md` - Task-level context (CLI implementation)
- `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t2_todo_cli/.claudiomiro/TASK1/PROMPT.md` - Task-specific context (code template, command specs)

**This file contains ONLY new information discovered during research.**

---

## Task Understanding Summary
Implement `src/todo_cli/cli.py` with four Click commands (add, list, complete, delete) and JSON storage functions. Foundation (TASK0) already complete with pyproject.toml and `__init__.py`.

---

## Similar Components Found (LEARN FROM THESE)

### 1. Complete CLI Implementation - `junior/t2_todo_cli/src/todo_cli/cli.py:1-165`
**Location:** `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/junior/t2_todo_cli/src/todo_cli/cli.py`

**Why similar:** Same todo CLI project. Fully working reference implementation.

**Patterns to reuse:**

#### Storage Functions - Lines 15-42
- `load_todos()` with empty file handling (line 28-30: checks `content.strip()`)
- `save_todos()` with `indent=2` for readable JSON
- **NOTE:** Reference uses `TODOS_FILE` constant (line 12), specs say `DATA_FILE`

#### Helper Functions - Lines 45-72
- `get_next_id()`: max ID + 1 or 1 if empty
- `find_todo()`: loop search returning todo or None

#### CLI Group - Line 75-78
- Uses `context_settings={"help_option_names": ["-h", "--help"]}` for additional help flag
- This is optional but nice UX

#### Output Format Discrepancy Found
**Reference implementation (line 106):**
```python
click.echo(f"Added todo #{new_todo['id']}: {description}")
```

**PROMPT.md:44 specifies:**
```
Output: "Added todo: {description}"
```

**Decision:** Follow PROMPT.md exactly - simpler format without ID in add output

#### Error Output Pattern - Lines 91-92, 134-135, 153-155
```python
click.echo("Error: Description cannot be empty.", err=True)
sys.exit(1)
```
- Uses `err=True` to write to stderr
- **Note:** PROMPT.md doesn't specify stderr, just exit code 1

#### Type Annotations - Throughout
- Uses `list[dict[str, Any]]` with `Any` import from typing
- Functions have `-> None` or `-> list[dict[str, Any]]` return types

### 2. Complete Test Suite - `junior/t2_todo_cli/tests/test_cli.py:1-277`
**Location:** `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/junior/t2_todo_cli/tests/test_cli.py`

**Why relevant:** Shows how TASK2 will test this CLI - helps ensure compatibility.

**Key patterns to ensure compatibility:**
- Line 8: `from todo_cli.cli import cli` - must export `cli` function
- Lines 17-21: Uses `monkeypatch.chdir(tmp_path)` for isolation
- Tests check for "Added", "Completed", "Deleted" in output (not exact match)
- Tests check `"not found" in result.output.lower()` (case-insensitive)

---

## Reusable Components (USE THESE, DON'T RECREATE)

### None from codebase
This task creates new code. No existing utilities to import.

### From Standard Library
- `json` - JSON serialization
- `sys` - `sys.exit(1)` for error exits
- `pathlib.Path` - File handling
- `datetime` - ISO timestamps

### From Dependencies
- `click` - Already in pyproject.toml from TASK0

---

## Codebase Conventions Discovered

### Output Message Format - Must Match Specs
| Command | Success Output (per PROMPT.md) |
|---------|-------------------------------|
| add | "Added todo: {description}" |
| complete | "Completed todo: {description}" |
| delete | "Deleted todo: {description}" |
| list | "{id}. [x] {desc}" or "{id}. [ ] {desc}" |

### Error Messages - Per PROMPT.md
| Error Case | Message |
|------------|---------|
| Empty description | "Error: Description cannot be empty" |
| Invalid ID | "Todo not found" |
| Empty list | "No todos yet" |

### File Naming
- `DATA_FILE = Path("todos.json")` per PROMPT.md:71

### Import Order (PEP 8)
1. Standard library (json, sys, pathlib, datetime)
2. Third-party (click)
3. Local (none for this file)

---

## Integration & Impact Analysis

### This Module is Called By:
1. **Entry point in pyproject.toml:** `todo = "todo_cli.cli:cli"`
   - Must export `cli` as Click group at module level

### This Module is Imported By:
1. **TASK2 tests:** `from todo_cli.cli import cli`
   - Tests invoke: `runner.invoke(cli, ['add', 'Test'])`

### Data File Contract:
- Creates/reads `todos.json` in current working directory
- Schema per AI_PROMPT.md:101-109:
  ```json
  {
    "id": 1,
    "description": "Buy groceries",
    "completed": false,
    "created_at": "2024-01-15T10:30:00"
  }
  ```

### Exit Code Contract:
| Result | Exit Code |
|--------|-----------|
| Success | 0 |
| Error (empty desc, invalid ID) | 1 |

---

## Test Strategy Discovered

### Testing Framework
- **Framework:** pytest
- **CLI Testing:** `click.testing.CliRunner`
- **Test file:** Will be `tests/test_cli.py` (TASK2)

### Test Patterns from Reference - `junior/t2_todo_cli/tests/test_cli.py`
- **Fixture pattern (lines 11-21):**
  ```python
  @pytest.fixture
  def runner():
      return CliRunner()

  @pytest.fixture
  def isolated_runner(runner, tmp_path, monkeypatch):
      monkeypatch.chdir(tmp_path)
      return runner
  ```
- **Invocation pattern:** `result = runner.invoke(cli, ['add', 'Task'])`
- **Assertions:** Check `result.exit_code` and `result.output`

### Key Test Assertions to Support:
- `"Added" in result.output` (not exact match)
- `"not found" in result.output.lower()`
- `"No todos yet" in result.output`
- `result.exit_code == 0` or `result.exit_code == 1`

---

## Risks & Challenges Identified

### Technical Risks

1. **Output Format Mismatch**
   - Impact: High (tests may fail)
   - Issue: Reference uses `"Added todo #{id}: ..."`, specs say `"Added todo: ..."`
   - Mitigation: Follow PROMPT.md specs exactly
   - Tests use substring matching, so both formats may pass

2. **Empty String vs Whitespace-Only**
   - Impact: Medium
   - Reference trims description and checks empty (line 89-92)
   - PROMPT.md says "empty description" error
   - Mitigation: `description.strip()` then check empty

3. **JSON File Read Error**
   - Impact: Low
   - Reference handles JSONDecodeError (line 32-33)
   - PROMPT.md code template doesn't include this
   - Decision: Keep simple per spec, don't add error handling not requested

### Complexity Assessment
- Overall: **Low-Medium**
- Reasoning: Clear specs and code template provided in PROMPT.md:63-111
  - 4 commands, each ~10-15 lines
  - 2 storage functions, each ~5 lines
  - Total ~80-100 lines

### Missing Information
- None - PROMPT.md provides complete code template at lines 63-111

---

## Execution Strategy Recommendation

**Based on research findings, execute in this order:**

1. **Create storage functions first**
   - Create: `src/todo_cli/cli.py`
   - Implement: `load_todos()`, `save_todos()`
   - Pattern from: PROMPT.md:73-79
   - Test: N/A (tested via commands)

2. **Create CLI group**
   - Implement: `@click.group()` with `cli()` function
   - Pattern from: PROMPT.md:81-84
   - Test: `uv run todo --help` shows usage

3. **Implement add command**
   - Implement: Validation, ID generation, save, output
   - Pattern from: PROMPT.md:86-91
   - Output: "Added todo: {description}"
   - Test: `uv run todo add "Test task"`

4. **Implement list command**
   - Implement: Load, format with checkboxes, handle empty
   - Pattern from: PROMPT.md:92-95
   - Output: "{id}. [x] desc" or "{id}. [ ] desc" or "No todos yet"
   - Test: `uv run todo list`

5. **Implement complete command**
   - Implement: Find by ID, update, save, handle not found
   - Pattern from: PROMPT.md:97-101
   - Output: "Completed todo: {description}" or "Todo not found"
   - Test: `uv run todo complete 1`

6. **Implement delete command**
   - Implement: Find by ID, remove, save, handle not found
   - Pattern from: PROMPT.md:103-108
   - Output: "Deleted todo: {description}" or "Todo not found"
   - Test: `uv run todo delete 1`

7. **Add main block**
   - Pattern from: PROMPT.md:109-110
   - `if __name__ == '__main__': cli()`

8. **Run verification**
   - Full workflow per PROMPT.md:130-140
   - Lint: `uv run ruff check src/todo_cli/cli.py`

---

**Research completed:** 2024-11-30
**Total similar components found:** 2 (cli.py implementation, test_cli.py patterns)
**Total reusable components identified:** 0 (creates new code, uses only stdlib + click)
**Estimated complexity:** Low-Medium
