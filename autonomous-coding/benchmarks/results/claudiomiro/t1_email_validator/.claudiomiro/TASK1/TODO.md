Fully implemented: NO

## Context Reference

**For complete environment context, read these files in order:**
1. `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/.claudiomiro/AI_PROMPT.md` - Universal context (tech stack: Python 3.11+, pytest, ruff, uv; architecture; conventions)
2. `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/.claudiomiro/TASK1/TASK.md` - Task-level context (what this task is about)
3. `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/.claudiomiro/TASK1/PROMPT.md` - Task-specific context (files to touch, patterns to follow)

**You MUST read these files before implementing to understand:**
- Tech stack: Python 3.11+, pytest, ruff, uv (no pip)
- Project structure: greenfield - create `email_validator.py` in project root
- Coding conventions: stdlib only, no regex, no external deps
- Function signature: `validate_email(email: str) -> bool`
- Validation rules: 11 rules specified in PROMPT.md (lines 4-17)
- Character sets: LOCAL_ALLOWED and DOMAIN_ALLOWED defined in PROMPT.md (lines 68-71)

**DO NOT duplicate this context below - it's already in the files above.**

## Implementation Plan

- [ ] **Item 1 — Create email_validator.py with validate_email function**
  - **What to do:**
    1. Create `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/email_validator.py`
    2. Define character sets at module level:
       ```python
       LOCAL_ALLOWED = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._%-+")
       DOMAIN_ALLOWED = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-")
       ```
    3. Implement `validate_email(email: str) -> bool` function with docstring
    4. Implement validation rules in this order (see PROMPT.md lines 4-17):
       - Check exactly one `@` symbol using `email.count('@') == 1`
       - Split using `email.split('@', 1)` to get local and domain parts
       - Check local part length: `1 <= len(local) <= 64`
       - Check domain part length: `1 <= len(domain) <= 255`
       - Check domain contains at least one dot: `'.' in domain`
       - Check no consecutive dots: `'..' not in email`
       - Check no leading/trailing dots in local: `not local.startswith('.') and not local.endswith('.')`
       - Check no leading/trailing dots in domain: `not domain.startswith('.') and not domain.endswith('.')`
       - Check all local chars in LOCAL_ALLOWED: `all(c in LOCAL_ALLOWED for c in local)`
       - Check all domain chars in DOMAIN_ALLOWED: `all(c in DOMAIN_ALLOWED for c in domain)`
    5. Run linting: `uv run ruff check email_validator.py && uv run ruff format --check email_validator.py`

  - **Context (read-only):**
    - `.claudiomiro/AI_PROMPT.md:51-62` — Function signature pattern
    - `.claudiomiro/TASK1/PROMPT.md:4-17` — Validation rules in order
    - `.claudiomiro/TASK1/PROMPT.md:68-71` — Character set definitions

  - **Touched (will modify/create):**
    - CREATE: `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/email_validator.py`

  - **Interfaces / Contracts:**
    - Export: `validate_email(email: str) -> bool`
    - Returns `True` for valid emails, `False` for invalid
    - No exceptions raised - pure boolean return

  - **Tests:**
    N/A for this item - tests are in a separate task (TASK2). However, manual verification:
    - `from email_validator import validate_email; assert validate_email("user@example.com") == True`
    - `from email_validator import validate_email; assert validate_email("invalid") == False`

  - **Migrations / Data:**
    N/A - No data changes

  - **Observability:**
    N/A - No observability requirements

  - **Security & Permissions:**
    - Input validation: Function handles any string input safely, returns False for malformed input
    - No PII handling concerns (just validation, no storage)

  - **Performance:**
    - Validation order optimized: cheap checks first (@ count, length) before expensive character iteration
    - O(n) complexity where n = email length
    - No performance concerns for typical email strings (<320 chars)

  - **Commands:**
    ```bash
    # Lint check
    uv run ruff check email_validator.py

    # Format check
    uv run ruff format --check email_validator.py

    # Quick manual test
    uv run python -c "from email_validator import validate_email; print(validate_email('user@example.com')); print(validate_email('invalid'))"
    ```

  - **Risks & Mitigations:**
    - **Risk:** Character set might be incomplete or incorrect
      **Mitigation:** Use exact sets from PROMPT.md lines 68-71
    - **Risk:** Edge cases with empty strings or None input
      **Mitigation:** Empty local/domain caught by length checks; function expects str type per signature

## Diff Test Plan

**Changed symbols:** `validate_email` function (new)

**Test cases required:**
| Scenario | Input | Expected | Notes |
|----------|-------|----------|-------|
| Happy path - simple email | `"user@example.com"` | `True` | Basic valid email |
| Happy path - dots in local | `"user.name@domain.co.uk"` | `True` | Multiple parts |
| Happy path - plus tag | `"user+tag@example.org"` | `True` | Plus sign allowed in local |
| Error - no local part | `"@example.com"` | `False` | Missing local |
| Error - no domain | `"user@"` | `False` | Missing domain |
| Error - double @ | `"user@@example.com"` | `False` | Multiple @ |
| Error - leading dot domain | `"user@.com"` | `False` | Dot at start of domain |
| Error - consecutive dots | `"user@example..com"` | `False` | Double dots |

**Coverage target:** 100% of validation branches

## Verification (global)
- [ ] Run lint for changed code only:
      ```bash
      uv run ruff check email_validator.py
      uv run ruff format --check email_validator.py
      ```
      CRITICAL: Do not run full-project checks
- [ ] Manual verification: import and test with valid/invalid emails
- [ ] All 11 validation rules implemented (see PROMPT.md lines 4-17)
- [ ] Function signature matches spec: `validate_email(email: str) -> bool`
- [ ] Code follows conventions from AI_PROMPT.md (no regex, stdlib only)

## Acceptance Criteria
- [ ] File `email_validator.py` exists in project root
- [ ] Function `validate_email(email: str) -> bool` is defined with proper type hints
- [ ] Function has docstring explaining its purpose
- [ ] All 11 validation rules are implemented (see PROMPT.md lines 4-17)
- [ ] Function returns `True` for valid emails, `False` for invalid
- [ ] No external dependencies used (stdlib only)
- [ ] No regex used (string methods only)
- [ ] `uv run ruff check email_validator.py` passes with no errors
- [ ] `uv run ruff format --check email_validator.py` passes with no errors

## Impact Analysis
- **Directly impacted:**
  - `email_validator.py` (new file)

- **Indirectly impacted:**
  - TASK2 (test_email_validator.py) depends on this module existing
  - Future tasks may import this function

## Follow-ups
- None identified - spec is complete and unambiguous
