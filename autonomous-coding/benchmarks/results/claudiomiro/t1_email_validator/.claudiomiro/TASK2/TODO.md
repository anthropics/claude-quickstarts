Fully implemented: NO

## Context Reference

**For complete environment context, read these files in order:**
1. `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/.claudiomiro/AI_PROMPT.md` - Universal context (tech stack, architecture, conventions)
2. `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/.claudiomiro/TASK2/TASK.md` - Task-level context (what this task is about)
3. `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/.claudiomiro/TASK2/PROMPT.md` - Task-specific context (files to touch, patterns to follow)

**You MUST read these files before implementing to understand:**
- Tech stack and framework versions (Python 3.11+, pytest, ruff, uv)
- Project structure and architecture
- Test patterns (AI_PROMPT.md lines 174-194)
- Required test cases (AI_PROMPT.md lines 98-109, 198-229)
- Test class structure and assertion style

**DO NOT duplicate this context below - it's already in the files above.**

## Implementation Plan

- [ ] **Item 1 — Create Test File with Valid Email Tests**
  - **What to do:**
    1. Create `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/test_email_validator.py`
    2. Add imports: `import pytest` and `from email_validator import validate_email`
    3. Create `TestValidEmails` class with docstring `"""Tests for emails that should be valid."""`
    4. Implement exactly 3 required valid email tests:
       - `test_simple_email`: assert `validate_email("user@example.com") is True`
       - `test_dotted_local_and_domain`: assert `validate_email("user.name@domain.co.uk") is True`
       - `test_plus_in_local`: assert `validate_email("user+tag@example.org") is True`

  - **Context (read-only):**
    - `AI_PROMPT.md:64-74` — Test import pattern
    - `AI_PROMPT.md:174-194` — Test class structure pattern
    - `AI_PROMPT.md:98-100` — Required valid email test cases
    - `AI_PROMPT.md:198-202` — Valid emails happy path

  - **Touched (will modify/create):**
    - CREATE: `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/test_email_validator.py`

  - **Interfaces / Contracts:**
    - Imports `validate_email` from `email_validator` module (created in TASK1)
    - Function signature: `validate_email(email: str) -> bool`
    - Returns `True` for valid emails

  - **Tests:**
    Type: Unit tests with pytest
    - Happy path: Simple email `user@example.com` → True
    - Happy path: Dotted local/domain `user.name@domain.co.uk` → True
    - Happy path: Plus sign in local `user+tag@example.org` → True

  - **Migrations / Data:**
    N/A - No data changes

  - **Observability:**
    N/A - No observability requirements

  - **Security & Permissions:**
    N/A - No security concerns

  - **Performance:**
    N/A - No performance requirements

  - **Commands:**
    ```bash
    # Run valid email tests only
    uv run pytest test_email_validator.py::TestValidEmails -v
    ```

  - **Risks & Mitigations:**
    - **Risk:** TASK1 (email_validator.py) not yet implemented
      **Mitigation:** Check if file exists; if not, document as blocker


- [ ] **Item 2 — Add Invalid Email Tests (Structural + Dot Issues)**
  - **What to do:**
    1. In `test_email_validator.py`, add `TestInvalidEmails` class with docstring `"""Tests for emails that should be invalid."""`
    2. Add structural issue tests:
       - `test_no_local_part`: `@example.com` → False
       - `test_no_domain`: `user@` → False
       - `test_double_at`: `user@@example.com` → False
       - `test_no_at_symbol`: `userexample.com` → False
       - `test_empty_string`: `""` → False
    3. Add dot issue tests:
       - `test_leading_dot_in_domain`: `user@.com` → False
       - `test_consecutive_dots_in_domain`: `user@example..com` → False
       - `test_leading_dot_in_local`: `.user@example.com` → False
       - `test_trailing_dot_in_local`: `user.@example.com` → False
       - `test_trailing_dot_in_domain`: `user@example.com.` → False
       - `test_consecutive_dots_in_local`: `user..name@example.com` → False

  - **Context (read-only):**
    - `AI_PROMPT.md:104-109` — Required invalid email test cases
    - `AI_PROMPT.md:204-216` — Invalid structural and dot issue cases
    - `AI_PROMPT.md:174-194` — Test class structure pattern

  - **Touched (will modify/create):**
    - MODIFY: `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/test_email_validator.py` — Add TestInvalidEmails class

  - **Interfaces / Contracts:**
    - Function `validate_email` returns `False` for all invalid cases
    - Each test is atomic and independent

  - **Tests:**
    Type: Unit tests with pytest
    - Structural: No local part (`@example.com`) → False
    - Structural: No domain (`user@`) → False
    - Structural: Double @ (`user@@example.com`) → False
    - Structural: No @ symbol (`userexample.com`) → False
    - Structural: Empty string (`""`) → False
    - Dot: Leading dot in domain (`user@.com`) → False
    - Dot: Consecutive dots in domain (`user@example..com`) → False
    - Dot: Leading dot in local (`.user@example.com`) → False
    - Dot: Trailing dot in local (`user.@example.com`) → False
    - Dot: Trailing dot in domain (`user@example.com.`) → False
    - Dot: Consecutive dots in local (`user..name@example.com`) → False

  - **Migrations / Data:**
    N/A - No data changes

  - **Observability:**
    N/A - No observability requirements

  - **Security & Permissions:**
    N/A - No security concerns

  - **Performance:**
    N/A - No performance requirements

  - **Commands:**
    ```bash
    # Run invalid email tests only
    uv run pytest test_email_validator.py::TestInvalidEmails -v
    ```

  - **Risks & Mitigations:**
    - **Risk:** Tests may fail if TASK1 implementation has bugs
      **Mitigation:** Each test is independent; identify failing tests and report


- [ ] **Item 3 — Add Edge Case Tests (Length, Character, Domain Structure)**
  - **What to do:**
    1. Add length issue tests to `TestInvalidEmails`:
       - `test_local_too_long`: `"a" * 65 + "@example.com"` → False
       - `test_domain_too_long`: `"user@" + "a" * 252 + ".com"` → False (256 chars total in domain)
    2. Add character issue tests:
       - `test_space_in_local`: `"user name@example.com"` → False
       - `test_space_in_domain`: `"user@exam ple.com"` → False
       - `test_disallowed_char_in_local`: `"user!@example.com"` → False
       - `test_disallowed_char_in_domain`: `"user@example#.com"` → False
    3. Add domain structure test:
       - `test_no_dot_in_domain`: `"user@example"` → False

  - **Context (read-only):**
    - `AI_PROMPT.md:218-229` — Length, character, and domain structure invalid cases
    - `PROMPT.md:47-54` — Edge case test data
    - `PROMPT.md:96-97` — Length test data construction

  - **Touched (will modify/create):**
    - MODIFY: `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/test_email_validator.py` — Add edge case tests to TestInvalidEmails

  - **Interfaces / Contracts:**
    - All edge case tests return `False`
    - Length tests use dynamically constructed strings

  - **Tests:**
    Type: Unit tests with pytest
    - Length: Local part > 64 chars → False
    - Length: Domain part > 255 chars → False
    - Character: Space in local → False
    - Character: Space in domain → False
    - Character: Disallowed char `!` in local → False
    - Character: Disallowed char `#` in domain → False
    - Domain: No dot in domain → False

  - **Migrations / Data:**
    N/A - No data changes

  - **Observability:**
    N/A - No observability requirements

  - **Security & Permissions:**
    N/A - No security concerns

  - **Performance:**
    N/A - No performance requirements

  - **Commands:**
    ```bash
    # Run all tests
    uv run pytest test_email_validator.py -v
    ```

  - **Risks & Mitigations:**
    - **Risk:** Length boundary off-by-one errors
      **Mitigation:** Verify exact lengths: local max = 64, domain max = 255


- [ ] **Item 4 — Verify with Ruff and Finalize**
  - **What to do:**
    1. Run ruff check on test file:
       ```bash
       uv run ruff check test_email_validator.py
       ```
    2. Fix any linting errors (imports, unused variables, etc.)
    3. Run ruff format check:
       ```bash
       uv run ruff format --check test_email_validator.py
       ```
    4. If formatting issues, run `uv run ruff format test_email_validator.py` to auto-fix
    5. Run full pytest suite to verify all tests pass:
       ```bash
       uv run pytest test_email_validator.py -v
       ```
    6. Confirm output shows all tests passing (0 failures)

  - **Context (read-only):**
    - `AI_PROMPT.md:251-260` — Verification commands
    - `AI_PROMPT.md:111-114` — Code quality acceptance criteria

  - **Touched (will modify/create):**
    - MODIFY: `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/test_email_validator.py` — Fix any linting/formatting issues

  - **Interfaces / Contracts:**
    - Ruff check passes with 0 errors
    - Ruff format check passes (no changes needed)
    - All pytest tests pass

  - **Tests:**
    Type: Verification (linting + test run)
    - Ruff check: 0 errors
    - Ruff format: No changes needed
    - Pytest: All tests pass (minimum 10 tests: 3 valid + 7+ invalid)

  - **Migrations / Data:**
    N/A - No data changes

  - **Observability:**
    N/A - No observability requirements

  - **Security & Permissions:**
    N/A - No security concerns

  - **Performance:**
    N/A - No performance requirements

  - **Commands:**
    ```bash
    # Lint check
    uv run ruff check test_email_validator.py

    # Format check
    uv run ruff format --check test_email_validator.py

    # Auto-fix format if needed
    uv run ruff format test_email_validator.py

    # Run all tests with verbose output
    uv run pytest test_email_validator.py -v
    ```

  - **Risks & Mitigations:**
    - **Risk:** Import errors if TASK1 not completed
      **Mitigation:** This is a dependency - TASK1 must be done first


## Verification (global)
- [ ] Run targeted tests ONLY for test file:
      ```bash
      uv run pytest test_email_validator.py -v
      uv run ruff check test_email_validator.py
      uv run ruff format --check test_email_validator.py
      ```
      **CRITICAL:** Do not run full-project checks (target only test_email_validator.py)
- [ ] All acceptance criteria met (see below)
- [ ] Code follows pytest conventions from AI_PROMPT.md (lines 174-194)
- [ ] Integration with email_validator.py works (import succeeds)
- [ ] Test count: minimum 10 tests (3 valid + 7 invalid/edge cases)

## Acceptance Criteria
- [ ] File `test_email_validator.py` exists in project root
- [ ] Imports pytest and validate_email correctly
- [ ] `TestValidEmails` class exists with exactly 3 tests (required valid emails)
- [ ] `TestInvalidEmails` class exists with at least 7 tests (required invalid + edge cases)
- [ ] Tests for required valid emails pass: `user@example.com`, `user.name@domain.co.uk`, `user+tag@example.org`
- [ ] Tests for required invalid emails pass: `@example.com`, `user@`, `user@@example.com`, `user@.com`, `user@example..com`
- [ ] Edge case tests included: length limits, character validation, domain structure
- [ ] All tests pass with `uv run pytest test_email_validator.py -v`
- [ ] Code passes `uv run ruff check test_email_validator.py`
- [ ] Code passes `uv run ruff format --check test_email_validator.py`

## Diff Test Plan
| Changed Symbol | Test Title | Arrange | Act | Assert |
|---------------|------------|---------|-----|--------|
| TestValidEmails.test_simple_email | Valid basic email | email = "user@example.com" | result = validate_email(email) | result is True |
| TestValidEmails.test_dotted_local_and_domain | Valid dotted email | email = "user.name@domain.co.uk" | result = validate_email(email) | result is True |
| TestValidEmails.test_plus_in_local | Valid plus tag | email = "user+tag@example.org" | result = validate_email(email) | result is True |
| TestInvalidEmails.test_no_local_part | No local part | email = "@example.com" | result = validate_email(email) | result is False |
| TestInvalidEmails.test_no_domain | No domain | email = "user@" | result = validate_email(email) | result is False |
| TestInvalidEmails.test_double_at | Multiple @ symbols | email = "user@@example.com" | result = validate_email(email) | result is False |
| TestInvalidEmails.test_leading_dot_in_domain | Leading dot domain | email = "user@.com" | result = validate_email(email) | result is False |
| TestInvalidEmails.test_consecutive_dots_in_domain | Consecutive dots | email = "user@example..com" | result = validate_email(email) | result is False |

## Impact Analysis
- **Directly impacted:**
  - `test_email_validator.py` (new file)

- **Indirectly impacted:**
  - TASKΩ depends on this task completing successfully
  - Must have working `email_validator.py` from TASK1 to run

## Follow-ups
- TASK1 must be completed before this task can run (dependency on `email_validator.py`)
- If tests fail, determine if issue is in tests or in TASK1 implementation
