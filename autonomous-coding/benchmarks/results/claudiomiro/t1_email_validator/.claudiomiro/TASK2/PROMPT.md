## PROMPT
Create `test_email_validator.py` with a comprehensive pytest test suite for the `validate_email` function. Cover all specified valid emails, invalid emails, and edge cases.

**Required Test Structure:**
```python
import pytest
from email_validator import validate_email


class TestValidEmails:
    """Tests for emails that should be valid."""

    def test_simple_email(self):
        assert validate_email("user@example.com") is True

    # ... more valid cases


class TestInvalidEmails:
    """Tests for emails that should be invalid."""

    def test_no_local_part(self):
        assert validate_email("@example.com") is False

    # ... more invalid cases
```

**Required Valid Email Tests:**
- `user@example.com` - basic valid email
- `user.name@domain.co.uk` - dots in local and multi-part domain
- `user+tag@example.org` - plus sign in local part

**Required Invalid Email Tests (minimum):**
- `@example.com` - no local part
- `user@` - no domain
- `user@@example.com` - double @
- `user@.com` - leading dot in domain
- `user@example..com` - consecutive dots

**Additional Edge Cases to Cover:**
- Empty string
- No @ symbol (`userexample.com`)
- Leading dot in local (`.user@example.com`)
- Trailing dot in local (`user.@example.com`)
- Trailing dot in domain (`user@example.com.`)
- Consecutive dots in local (`user..name@example.com`)
- Local part > 64 characters
- Domain part > 255 characters
- Space in local part
- Space in domain
- Disallowed character in local (`user!@example.com`)
- Disallowed character in domain (`user@example#.com`)
- No dot in domain (`user@example`)

After implementation, verify with:
```bash
uv run pytest test_email_validator.py -v
uv run ruff check test_email_validator.py
uv run ruff format --check test_email_validator.py
```

## COMPLEXITY
Low

## CONTEXT REFERENCE
**For complete environment context, read:**
- `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/.claudiomiro/AI_PROMPT.md` - Contains full tech stack, test patterns (lines 174-194), required test cases (lines 198-229)

**You MUST read AI_PROMPT.md before executing this task to understand the environment.**

## TASK-SPECIFIC CONTEXT

### Files This Task Will Touch
- CREATE: `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/test_email_validator.py`

### Patterns to Follow
- Test class structure from AI_PROMPT.md (lines 174-194)
- pytest style assertions: `assert ... is True`, `assert ... is False`
- Test method naming: `test_<descriptive_name>`

### Integration Points
- Imports `validate_email` from `email_validator` (created in TASK1)
- Run with `uv run pytest test_email_validator.py -v`

## EXTRA DOCUMENTATION

**Test Categories:**
1. Valid emails (happy path) - should return True
2. Invalid - structural issues - missing parts, multiple @
3. Invalid - dot issues - leading, trailing, consecutive
4. Invalid - length issues - too long local/domain
5. Invalid - character issues - spaces, disallowed chars
6. Invalid - domain structure - no dot in domain

**Length Test Data:**
- Local > 64: `"a" * 65 + "@example.com"`
- Domain > 255: `"user@" + "a" * 252 + ".com"` (256 chars after @)

## LAYER
1

## PARALLELIZATION
Parallel with: None (depends on TASK1)

## CONSTRAINTS
- IMPORTANT: Do not perform any git commit or git push.
- Must import from `email_validator` module (TASK1)
- Use pytest style (not unittest)
- Use test classes for organization
- Each test should be atomic and independent
- Verify with ruff check and ruff format before completion
- Run pytest to confirm all tests pass
