@dependencies [TASK1]
# Task: Final Ω Assembly Validation - T0 Validation Complete System Check

## Summary
Perform final validation to ensure the T0 validation test passes all acceptance criteria. This task verifies that `hello.py` exists, executes correctly, and produces the expected JSON output. This is the mandatory system-level validation step that confirms the entire pipeline worked correctly.

## Context Reference
**For complete environment context, see:**
- `../AI_PROMPT.md` - Contains full tech stack, acceptance criteria, and verification commands

**Task-Specific Context:**

### Files This Task Will Validate
- `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t0_validation/hello.py` (created by TASK1)

### Verification Commands to Run
- Simple execution: `python hello.py`
- Full validation: `python hello.py | python -c "import json,sys; d=json.load(sys.stdin); assert d['status']=='ok'; assert d['message'].startswith('Hello from '); print('PASS')"`

### Task-Specific Constraints
- This task performs READ-ONLY validation - do NOT modify any files
- All tests must pass for the T0 validation to be considered successful

## Complexity
Low

## Dependencies
Depends on: [TASK1]
Blocks: []
Parallel with: []

## Detailed Steps
1. Verify `hello.py` exists at the project root
2. Run `python hello.py` and capture output
3. Verify exit code is 0 (no errors)
4. Verify output is valid JSON
5. Verify JSON contains `"status": "ok"`
6. Verify JSON contains `"message"` starting with `"Hello from "`
7. Verify no stderr output
8. Run the full verification command from AI_PROMPT.md
9. Report final validation status

## Acceptance Criteria
- [ ] File `hello.py` exists at project root
- [ ] `python hello.py` exits with code 0
- [ ] Output is single-line valid JSON
- [ ] JSON has `status` key with value `"ok"`
- [ ] JSON has `message` key starting with `"Hello from "`
- [ ] No stderr output
- [ ] Full verification command prints `PASS`
- [ ] No requirements from AI_PROMPT.md were missed

## Code Review Checklist
- [ ] All acceptance criteria from AI_PROMPT.md section 4 are verified
- [ ] All items in self-verification checklist from AI_PROMPT.md section 6 are checked
- [ ] No extra files were created (only `hello.py`)
- [ ] Script uses only Python standard library

## Reasoning Trace
This final validation task ensures the T0 sanity check is complete and successful. Since this is the simplest possible validation test, failure here would indicate a fundamental problem with the autonomous coding pipeline itself.

The validation is comprehensive but simple:
1. Existence check (file was created)
2. Execution check (script runs without error)
3. Output check (valid JSON with correct structure)
4. No side effects check (no extra files, no stderr)

All these checks are explicitly defined in AI_PROMPT.md sections 4 and 6.
