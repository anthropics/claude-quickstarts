# AI_PROMPT.md — Email Validator Function Implementation

## 🎯 Purpose

**What:** Implement a standalone Python email validation function with comprehensive tests.

**Ultimate Goal:** Create a `validate_email(email: str) -> bool` function that correctly validates email addresses according to specific rules, along with a complete pytest test suite.

**Success Definition:** Both files pass all tests, pass ruff linting/formatting checks, and correctly handle all specified valid/invalid email cases.

---

## 📁 Environment & Codebase Context

### Tech Stack
- **Language:** Python 3.11+
- **Testing:** pytest
- **Linting/Formatting:** ruff
- **Dependencies:** None (stdlib only)
- **Package Manager:** uv (use `uv run pytest` to run tests)

### Project Structure
```
/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/
├── .claudiomiro/           # Task metadata (do not modify)
│   ├── AI_PROMPT.md        # This file
│   ├── INITIAL_PROMPT.md   # Original task
│   └── log.txt             # Task log
├── email_validator.py      # TO CREATE: Main module
└── test_email_validator.py # TO CREATE: Test file
```

### Current State
- **Git Branch:** `task/t1-email-validator` (already created)
- **Existing Files:** None in the root directory - this is a greenfield implementation
- **No existing code patterns** to follow - this is a standalone benchmark task

### Environment Notes
- Use `uv run pytest test_email_validator.py -v` to run tests
- Use `uv run ruff check .` and `uv run ruff format --check .` for linting
- Commit after creating/modifying files

---

## 🧩 Related Code Context

This is a standalone task with no related codebase. However, for reference:

**Email Validation Pattern (example approach):**
```python
def validate_email(email: str) -> bool:
    """Validate email address according to specified rules.

    Args:
        email: The email address to validate.

    Returns:
        True if valid, False otherwise.
    """
    # Implementation here
    pass
```

**Test Pattern (pytest style):**
```python
import pytest
from email_validator import validate_email

def test_valid_email_simple():
    assert validate_email("user@example.com") is True

def test_invalid_email_no_at():
    assert validate_email("userexample.com") is False
```

---

## ✅ Acceptance Criteria

### Core Functionality
- [ ] Function `validate_email(email: str) -> bool` exists in `email_validator.py`
- [ ] Function returns `True` for valid emails, `False` for invalid
- [ ] Function has proper type hints

### Validation Rules (ALL must be enforced)
- [ ] Exactly one `@` symbol required
- [ ] Local part (before @) must be 1-64 characters long
- [ ] Domain part (after @) must be 1-255 characters long
- [ ] Domain must contain at least one dot (`.`)
- [ ] No consecutive dots (`..`) allowed anywhere
- [ ] No leading dot in local part (e.g., `.user@example.com` → invalid)
- [ ] No trailing dot in local part (e.g., `user.@example.com` → invalid)
- [ ] No leading dot in domain part (e.g., `user@.example.com` → invalid)
- [ ] No trailing dot in domain part (e.g., `user@example.com.` → invalid)
- [ ] Only allowed characters: `a-z`, `A-Z`, `0-9`, `.`, `_`, `%`, `+`, `-`

### Required Test Cases
**Must pass (valid emails):**
- [ ] `user@example.com`
- [ ] `user.name@domain.co.uk`
- [ ] `user+tag@example.org`

**Must fail (invalid emails):**
- [ ] `@example.com` (no local part)
- [ ] `user@` (no domain)
- [ ] `user@@example.com` (double @)
- [ ] `user@.com` (leading dot in domain)
- [ ] `user@example..com` (consecutive dots)

### Code Quality
- [ ] Passes `ruff check .` with no errors
- [ ] Passes `ruff format --check .` with no errors
- [ ] All pytest tests pass
- [ ] Code has docstrings explaining the function

---

## ⚙️ Implementation Guidance

### Execution Layers

**Layer 0 - Foundation:**
1. Create `email_validator.py` with the `validate_email` function
2. Implement all validation rules in order of simplicity

**Layer 1 - Testing:**
1. Create `test_email_validator.py` with pytest tests
2. Cover all required valid/invalid cases
3. Add edge case tests

**Layer 2 - Validation:**
1. Run `uv run pytest test_email_validator.py -v`
2. Run `uv run ruff check .`
3. Run `uv run ruff format --check .`
4. Fix any issues

### Implementation Approach

**Recommended validation order (in function):**
1. Check for exactly one `@` symbol (reject if not)
2. Split into local and domain parts
3. Check local part length (1-64)
4. Check domain part length (1-255)
5. Check domain has at least one dot
6. Check no consecutive dots anywhere
7. Check no leading/trailing dots in local part
8. Check no leading/trailing dots in domain part
9. Check all characters are in allowed set

**Character validation:**
- Allowed in both local and domain: `a-z`, `A-Z`, `0-9`, `.`, `-`
- Allowed ONLY in local part: `_`, `%`, `+`
- The `@` symbol is the separator (already validated)

### Expected Artifacts

| File | Purpose |
|------|---------|
| `email_validator.py` | Main module with `validate_email` function |
| `test_email_validator.py` | Comprehensive pytest test suite |

### Constraints
- **DO NOT** use external email validation libraries
- **DO NOT** use `re` module for regex (use string methods for simplicity and clarity)
- **DO NOT** create additional helper files
- **DO NOT** over-engineer - keep it simple and readable
- **DO NOT** add features beyond what's specified

---

## 🧪 Testing Guidance

### Test Structure
```python
# test_email_validator.py
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

### Required Test Categories

**1. Valid emails (happy path):**
- `user@example.com` - basic valid
- `user.name@domain.co.uk` - dots in local and multi-part domain
- `user+tag@example.org` - plus sign in local part

**2. Invalid - structural issues:**
- `@example.com` - missing local part
- `user@` - missing domain
- `user@@example.com` - multiple @ symbols
- `userexample.com` - no @ symbol
- Empty string

**3. Invalid - dot issues:**
- `user@.com` - leading dot in domain
- `.user@example.com` - leading dot in local
- `user.@example.com` - trailing dot in local
- `user@example.com.` - trailing dot in domain
- `user@example..com` - consecutive dots in domain
- `user..name@example.com` - consecutive dots in local

**4. Invalid - length issues:**
- Local part > 64 chars
- Domain part > 255 chars
- Empty local part (just `@domain.com`)
- Empty domain part (just `user@`)

**5. Invalid - character issues:**
- `user name@example.com` - space
- `user@exam ple.com` - space in domain
- `user!@example.com` - disallowed character
- `user@example#.com` - disallowed character in domain

**6. Invalid - domain structure:**
- `user@example` - no dot in domain

### Minimum Test Count
- At least 3 valid email tests (as specified)
- At least 5 invalid email tests (as specified)
- Additional edge case tests recommended

---

## 🔍 Verification and Traceability

### Pre-Completion Checklist

Before marking complete, verify:

1. **Files exist:**
   - [ ] `email_validator.py` created in project root
   - [ ] `test_email_validator.py` created in project root

2. **Tests pass:**
   ```bash
   uv run pytest test_email_validator.py -v
   ```
   - [ ] All tests pass (0 failures)

3. **Linting passes:**
   ```bash
   uv run ruff check .
   uv run ruff format --check .
   ```
   - [ ] No ruff errors
   - [ ] No formatting issues

4. **Manual spot check:**
   ```python
   from email_validator import validate_email
   assert validate_email("user@example.com") == True
   assert validate_email("invalid") == False
   ```

5. **Git commit:**
   - [ ] Changes committed to `task/t1-email-validator` branch

### Requirement Traceability

| Original Requirement | Implementation Location |
|---------------------|------------------------|
| Function signature | `email_validator.py` - function definition |
| Exactly one @ | Validation step in function |
| Local part 1-64 chars | Validation step in function |
| Domain part 1-255 chars | Validation step in function |
| Domain has dot | Validation step in function |
| No consecutive dots | Validation step in function |
| No leading/trailing dots | Validation step in function |
| Allowed characters only | Validation step in function |
| Valid test cases | `test_email_validator.py` - TestValidEmails |
| Invalid test cases | `test_email_validator.py` - TestInvalidEmails |

---

## 🧠 Reasoning Boundaries

### Keep It Simple
- This is a trivial complexity task - don't over-engineer
- Use simple string methods, not regex
- One function, one file, one test file
- No need for classes in the main module (just a function)

### Don't Add
- Command-line interfaces
- Additional validation beyond what's specified
- Custom exceptions (just return bool)
- Logging
- Configuration options
- Additional helper functions (unless truly necessary for readability)

### Decision Points
- If unsure whether a character is "allowed", refer to the spec: `a-z, A-Z, 0-9, . _ % + -`
- If unsure about edge cases not covered in tests, implement the safest interpretation that follows the rules

---

## 📋 Summary

**Create two files:**

1. **`email_validator.py`** containing:
   - `validate_email(email: str) -> bool` function
   - Implements all 8 validation rules
   - Uses only stdlib (no external deps)
   - Clean, documented code

2. **`test_email_validator.py`** containing:
   - pytest tests for all specified valid emails
   - pytest tests for all specified invalid emails
   - Additional edge case coverage

**Verify with:**
```bash
uv run pytest test_email_validator.py -v
uv run ruff check .
uv run ruff format --check .
```

**Commit when complete.**
