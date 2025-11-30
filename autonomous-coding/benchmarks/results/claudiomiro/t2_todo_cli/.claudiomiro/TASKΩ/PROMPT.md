## PROMPT
Perform comprehensive end-to-end validation of the complete todo CLI application. Run all tests, verify linting passes, manually test all commands, verify edge case handling, and confirm all acceptance criteria from AI_PROMPT.md are met. This is the final system-level validation.

## COMPLEXITY
Low

## CONTEXT REFERENCE
**For complete environment context, read:**
- `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t2_todo_cli/.claudiomiro/AI_PROMPT.md` - Contains full verification checklist (section 6), self-verification steps, traceability matrix, and all acceptance criteria

**You MUST read AI_PROMPT.md before executing this task to understand all requirements that must be validated.**

## TASK-SPECIFIC CONTEXT

### Files This Task Will Validate (not create)
- `src/todo_cli/cli.py` - Main CLI implementation
- `tests/test_cli.py` - Test suite
- `pyproject.toml` - Package configuration
- `todos.json` - Created during manual testing

### Verification Checklist
From AI_PROMPT.md section 6:
1. Test validation
2. Linting validation
3. Manual command verification
4. Edge case verification
5. Data structure verification

## EXTRA DOCUMENTATION

### Validation Commands to Execute

**1. Test Suite:**
```bash
uv run pytest -v
# Expected: 10+ tests, all passing
```

**2. Linting:**
```bash
uv run ruff check src/ tests/
# Expected: No errors
```

**3. Manual Command Tests (execute in order):**
```bash
# Clean slate
rm -f todos.json

# Add command
uv run todo add "Buy groceries"
echo $?  # Should be 0

# List command
uv run todo list
# Should show: 1. [ ] Buy groceries

# Complete command
uv run todo complete 1
echo $?  # Should be 0

# List after complete
uv run todo list
# Should show: 1. [x] Buy groceries

# Delete command
uv run todo delete 1
echo $?  # Should be 0

# List after delete
uv run todo list
# Should show: No todos yet

# Help command
uv run todo --help
# Should show usage info
```

**4. Edge Case Tests:**
```bash
# Empty description
uv run todo add ""
echo $?  # Should be 1

# Invalid ID on complete
uv run todo complete 999
echo $?  # Should be 1
# Output should contain "Todo not found"

# Invalid ID on delete
uv run todo delete 999
echo $?  # Should be 1
# Output should contain "Todo not found"
```

**5. Data Structure Verification:**
```bash
# After adding a todo, check JSON structure
uv run todo add "Verify structure"
cat todos.json
# Should contain: id, description, completed, created_at
```

### Traceability Matrix (AI_PROMPT.md:302-313)
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

## LAYER
Ω (Final)

## PARALLELIZATION
Parallel with: None

## CONSTRAINTS
- IMPORTANT: Do not perform any git commit or git push.
- This task is validation only - do NOT modify any source files
- If any validation fails, document the failure clearly but do NOT attempt fixes (report back instead)
- All validation must pass for task completion

## VALIDATION
Task is complete when:
1. `uv run pytest` shows 10+ tests passing
2. `uv run ruff check src/ tests/` shows no errors
3. All manual command tests produce expected output
4. All edge cases handled correctly with exit code 1
5. JSON data structure matches specification
