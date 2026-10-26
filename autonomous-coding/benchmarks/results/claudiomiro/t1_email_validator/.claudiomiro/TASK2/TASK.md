@dependencies [TASK1]
# Task: Create Comprehensive Test Suite

## Summary
Create `test_email_validator.py` with a complete pytest test suite covering all specified valid emails, invalid emails, and edge cases. The tests verify that the `validate_email` function correctly implements all validation rules.

## Context Reference
**For complete environment context, see:**
- `../AI_PROMPT.md` - Contains full tech stack (pytest, ruff), test patterns (lines 64-74, 174-194), required test cases (lines 98-109, 198-229)

**Task-Specific Context:**
- File to create: `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/test_email_validator.py`
- Imports: `pytest` and `from email_validator import validate_email`
- Test structure: Use test classes `TestValidEmails` and `TestInvalidEmails`
- Follow pytest patterns from AI_PROMPT.md (lines 174-194)

## Complexity
Low

## Dependencies
Depends on: TASK1 (needs `email_validator.py` to exist)
Blocks: TASKΩ
Parallel with: None

## Detailed Steps
1. Create `test_email_validator.py` in project root
2. Import pytest and validate_email function
3. Create `TestValidEmails` class with tests:
   - `test_simple_email` - `user@example.com`
   - `test_dotted_local_and_domain` - `user.name@domain.co.uk`
   - `test_plus_in_local` - `user+tag@example.org`
4. Create `TestInvalidEmails` class with tests for:
   - Structural issues: no local part, no domain, multiple @, no @, empty string
   - Dot issues: leading/trailing dots, consecutive dots
   - Length issues: local > 64 chars, domain > 255 chars
   - Character issues: spaces, disallowed characters
   - Domain structure: no dot in domain
5. Verify all tests pass

## Acceptance Criteria
- [ ] File `test_email_validator.py` exists in project root
- [ ] Imports pytest and validate_email correctly
- [ ] `TestValidEmails` class exists with at least 3 tests
- [ ] `TestInvalidEmails` class exists with at least 5 tests
- [ ] Tests for all 3 required valid emails pass
- [ ] Tests for all 5 required invalid emails pass
- [ ] Edge case tests included (as listed in AI_PROMPT.md lines 198-229)
- [ ] All tests pass with `uv run pytest test_email_validator.py -v`
- [ ] Code passes `ruff check test_email_validator.py`
- [ ] Code passes `ruff format --check test_email_validator.py`

## Code Review Checklist
- [ ] Test class names are descriptive (TestValidEmails, TestInvalidEmails)
- [ ] Test method names clearly indicate what is being tested
- [ ] Uses `assert ... is True` and `assert ... is False` for clarity
- [ ] Each test is independent (no shared state)
- [ ] No unnecessary fixtures or setup
- [ ] Tests are organized logically by category
- [ ] Class docstrings explain the category being tested

## Reasoning Trace
Tests are organized into classes by expected outcome (valid vs invalid) for clarity. Each test is atomic - testing one specific case. The test naming convention follows `test_<what_is_being_tested>` pattern.

Edge cases are critical for email validation:
- Empty strings and missing parts test boundary conditions
- Length limits test off-by-one errors
- Character validation tests ensure the allowed set is correctly defined
- Dot position tests catch common implementation bugs
