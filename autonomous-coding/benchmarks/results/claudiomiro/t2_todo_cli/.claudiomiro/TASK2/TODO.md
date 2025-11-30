Fully implemented: NO

## Context Reference

**For complete environment context, read these files in order:**
1. `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t2_todo_cli/.claudiomiro/AI_PROMPT.md` - Universal context (tech stack, architecture, conventions, testing patterns)
2. `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t2_todo_cli/.claudiomiro/TASK2/TASK.md` - Task-level context (what this task is about)
3. `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t2_todo_cli/.claudiomiro/TASK2/PROMPT.md` - Task-specific context (files to touch, patterns to follow)

**You MUST read these files before implementing to understand:**
- Tech stack: Python 3.11+, pytest for testing, Click's CliRunner for CLI testing
- Testing patterns: CliRunner with `isolated_filesystem()` for test isolation
- Test structure: 10+ tests covering happy paths (4), edge cases (4), integration (2)
- Related code examples with file:line references in AI_PROMPT.md:254-271

**DO NOT duplicate this context below - it's already in the files above.**

## Implementation Plan

- [ ] **Item 1 — Create Test Suite with Happy Path Tests (4 tests)**
  - **What to do:**
    1. Create `tests/test_cli.py` file
    2. Add imports: `from click.testing import CliRunner` and `from todo_cli.cli import cli`
    3. Implement `test_add_todo()`:
       - Create CliRunner, use `isolated_filesystem()`
       - Invoke `['add', 'Buy groceries']`
       - Assert exit_code == 0, 'Added' in output
    4. Implement `test_list_todos()`:
       - Add a todo first, then invoke `['list']`
       - Assert exit_code == 0, todo description in output, `[ ]` checkbox format
    5. Implement `test_complete_todo()`:
       - Add a todo, then invoke `['complete', '1']`
       - Assert exit_code == 0, 'Completed' in output
    6. Implement `test_delete_todo()`:
       - Add a todo, then invoke `['delete', '1']`
       - Assert exit_code == 0, 'Deleted' in output

  - **Context (read-only):**
    - `AI_PROMPT.md:254-266` — CliRunner test pattern with isolated_filesystem
    - `AI_PROMPT.md:237-252` — Happy path test specifications
    - `PROMPT.md:32-52` — Test function templates

  - **Touched (will modify/create):**
    - CREATE: `tests/test_cli.py`

  - **Interfaces / Contracts:**
    - Import: `from todo_cli.cli import cli` (Click group)
    - Import: `from click.testing import CliRunner`
    - CLI contract: `cli` is a Click group with commands: add, list, complete, delete

  - **Tests:**
    Type: unit tests with pytest + Click CliRunner
    - `test_add_todo`: Add 'Buy groceries' → exit 0, 'Added' in output
    - `test_list_todos`: Add → List → exit 0, description shown with `[ ]`
    - `test_complete_todo`: Add → Complete 1 → exit 0, 'Completed' in output
    - `test_delete_todo`: Add → Delete 1 → exit 0, 'Deleted' in output

  - **Migrations / Data:**
    N/A - Tests use isolated filesystem

  - **Observability:**
    N/A - No observability requirements

  - **Security & Permissions:**
    N/A - No security concerns

  - **Performance:**
    N/A - No performance requirements

  - **Commands:**
    ```bash
    # Run specific tests after creation
    uv run pytest tests/test_cli.py::test_add_todo -v
    uv run pytest tests/test_cli.py::test_list_todos -v
    uv run pytest tests/test_cli.py::test_complete_todo -v
    uv run pytest tests/test_cli.py::test_delete_todo -v
    ```

  - **Risks & Mitigations:**
    - **Risk:** Import error if cli.py not created yet (TASK1 incomplete)
      **Mitigation:** Verify TASK1 is complete before running tests
    - **Risk:** Isolated filesystem not properly cleaning up
      **Mitigation:** Use context manager `with runner.isolated_filesystem():`

- [ ] **Item 2 — Add Edge Case Tests (4 tests)**
  - **What to do:**
    1. Implement `test_add_empty_description()`:
       - Invoke `['add', '']`
       - Assert exit_code == 1, error message in output
    2. Implement `test_complete_invalid_id()`:
       - Invoke `['complete', '999']` (no todos exist)
       - Assert exit_code == 1, 'Todo not found' in output
    3. Implement `test_delete_invalid_id()`:
       - Invoke `['delete', '999']` (no todos exist)
       - Assert exit_code == 1, 'Todo not found' in output
    4. Implement `test_list_empty()`:
       - Invoke `['list']` on fresh filesystem
       - Assert exit_code == 0, 'No todos yet' in output

  - **Context (read-only):**
    - `AI_PROMPT.md:253-257` — Edge case test specifications
    - `PROMPT.md:54-71` — Edge case test templates
    - `AI_PROMPT.md:135-138` — Edge case behavior requirements

  - **Touched (will modify/create):**
    - MODIFY: `tests/test_cli.py` (add 4 functions)

  - **Interfaces / Contracts:**
    - Same imports as Item 1
    - Error behavior: exit code 1 for invalid operations
    - Empty list message: "No todos yet"
    - Invalid ID message: "Todo not found"

  - **Tests:**
    Type: unit tests with pytest + Click CliRunner
    - `test_add_empty_description`: Add '' → exit 1, error message
    - `test_complete_invalid_id`: Complete 999 → exit 1, 'Todo not found'
    - `test_delete_invalid_id`: Delete 999 → exit 1, 'Todo not found'
    - `test_list_empty`: List (no todos) → exit 0, 'No todos yet'

  - **Migrations / Data:**
    N/A - Tests use isolated filesystem

  - **Observability:**
    N/A - No observability requirements

  - **Security & Permissions:**
    N/A - No security concerns

  - **Performance:**
    N/A - No performance requirements

  - **Commands:**
    ```bash
    # Run edge case tests
    uv run pytest tests/test_cli.py::test_add_empty_description -v
    uv run pytest tests/test_cli.py::test_complete_invalid_id -v
    uv run pytest tests/test_cli.py::test_delete_invalid_id -v
    uv run pytest tests/test_cli.py::test_list_empty -v
    ```

  - **Risks & Mitigations:**
    - **Risk:** CLI might not return exit code 1 for errors
      **Mitigation:** Verify cli.py uses `sys.exit(1)` for errors
    - **Risk:** Error messages might differ from expected
      **Mitigation:** Use partial string matching (e.g., 'not found' instead of exact match)

- [ ] **Item 3 — Add Integration Tests (2 tests)**
  - **What to do:**
    1. Implement `test_persistence()`:
       - Add 'Task 1', then invoke list in separate invocation
       - Assert task persists across invocations
    2. Implement `test_complete_workflow()`:
       - Add 'Task 1' → Complete 1 → List
       - Assert `[x]` appears in list output (completed status)

  - **Context (read-only):**
    - `AI_PROMPT.md:258-266` — Integration test specifications
    - `PROMPT.md:73-91` — Integration test templates
    - `AI_PROMPT.md:129` — List output format with checkboxes

  - **Touched (will modify/create):**
    - MODIFY: `tests/test_cli.py` (add 2 functions)

  - **Interfaces / Contracts:**
    - Data persistence: todos.json created in working directory
    - Checkbox format: `[x]` for completed, `[ ]` for pending

  - **Tests:**
    Type: integration tests with pytest + Click CliRunner
    - `test_persistence`: Add → separate List → task visible
    - `test_complete_workflow`: Add → Complete → List → `[x]` visible

  - **Migrations / Data:**
    N/A - Tests use isolated filesystem

  - **Observability:**
    N/A - No observability requirements

  - **Security & Permissions:**
    N/A - No security concerns

  - **Performance:**
    N/A - No performance requirements

  - **Commands:**
    ```bash
    # Run integration tests
    uv run pytest tests/test_cli.py::test_persistence -v
    uv run pytest tests/test_cli.py::test_complete_workflow -v
    ```

  - **Risks & Mitigations:**
    - **Risk:** Isolated filesystem might reset between invocations
      **Mitigation:** All invocations must be within same `with runner.isolated_filesystem():` block

- [ ] **Item 4 — Run Full Test Suite and Verify**
  - **What to do:**
    1. Run all tests with verbose output
    2. Verify all 10 tests pass
    3. Run linter on test file
    4. Fix any failures or lint issues

  - **Context (read-only):**
    - `PROMPT.md:127-138` — Validation commands and expected output

  - **Touched (will modify/create):**
    - MODIFY: `tests/test_cli.py` (if fixes needed)

  - **Interfaces / Contracts:**
    N/A - Verification step

  - **Tests:**
    Type: Full test suite execution
    - All 10 tests must pass
    - 100% pass rate required

  - **Migrations / Data:**
    N/A

  - **Observability:**
    N/A

  - **Security & Permissions:**
    N/A

  - **Performance:**
    N/A

  - **Commands:**
    ```bash
    # Full test suite
    uv run pytest tests/test_cli.py -v

    # With short traceback for failures
    uv run pytest tests/test_cli.py --tb=short

    # Lint test file
    uv run ruff check tests/test_cli.py

    # Expected output:
    # tests/test_cli.py .......... [100%]
    # 10 passed
    ```

  - **Risks & Mitigations:**
    - **Risk:** TASK0 or TASK1 incomplete
      **Mitigation:** Verify src/todo_cli/cli.py exists before running tests

## Verification (global)
- [ ] Run targeted tests ONLY for changed code:
      ```bash
      uv run pytest tests/test_cli.py -v
      uv run ruff check tests/test_cli.py
      ```
      **CRITICAL:** Do not run full-project checks (target only tests/)
- [ ] All acceptance criteria met (see below)
- [ ] Code follows conventions from AI_PROMPT.md and PROMPT.md
- [ ] Every test uses `runner.isolated_filesystem()` for isolation
- [ ] Tests check both `exit_code` and `output`
- [ ] No shared state between tests

## Acceptance Criteria
- [ ] At least 10 tests in `tests/test_cli.py`
- [ ] Tests cover all commands: add (test_add_todo), list (test_list_todos, test_list_empty), complete (test_complete_todo), delete (test_delete_todo)
- [ ] Tests cover edge cases: empty description, invalid ID (2x), empty list
- [ ] Happy path tests pass (4): test_add_todo, test_list_todos, test_complete_todo, test_delete_todo
- [ ] Edge case tests pass (4): test_add_empty_description, test_complete_invalid_id, test_delete_invalid_id, test_list_empty
- [ ] Integration tests pass (2): test_persistence, test_complete_workflow
- [ ] All tests use CliRunner with `isolated_filesystem()`
- [ ] All tests are independent (no shared state)
- [ ] `uv run pytest tests/test_cli.py` shows 10 passed
- [ ] `uv run ruff check tests/test_cli.py` shows no errors

## Diff Test Plan
| Changed Symbol | Happy Path | Edge Cases | Failure Case |
|----------------|------------|------------|--------------|
| test_add_todo | Add valid description → exit 0 | - | - |
| test_list_todos | Add → List → shows task | - | - |
| test_complete_todo | Add → Complete → exit 0 | - | - |
| test_delete_todo | Add → Delete → exit 0 | - | - |
| test_add_empty_description | - | Empty string → exit 1 | - |
| test_complete_invalid_id | - | ID 999 → 'not found', exit 1 | - |
| test_delete_invalid_id | - | ID 999 → 'not found', exit 1 | - |
| test_list_empty | - | No todos → 'No todos yet' | - |
| test_persistence | Add → List in separate call → persists | - | - |
| test_complete_workflow | Add → Complete → List → [x] | - | - |

## Impact Analysis
- **Directly impacted:**
  - `tests/test_cli.py` (new file - 10 test functions)

- **Indirectly impacted:**
  - TASKΩ (Final Validation) depends on these tests passing
  - No downstream file changes needed

## Follow-ups
- None identified
