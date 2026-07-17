# Research for TASK1

## Context Reference
**For tech stack and conventions, see:**
- `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/.claudiomiro/AI_PROMPT.md` - Universal context
- `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/.claudiomiro/TASK1/TASK.md` - Task-level context
- `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/.claudiomiro/TASK1/PROMPT.md` - Task-specific context

**This file contains ONLY new information discovered during research.**

---

## Task Understanding Summary
Create `email_validator.py` with `validate_email(email: str) -> bool` function implementing 11 validation rules using stdlib only (NO regex). See TODO.md for full implementation plan.

---

## Similar Components Found (LEARN FROM THESE)

### 1. Junior Benchmark Implementation - `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/junior/t1_email_validator/email_validator.py`

**Why similar:** Identical task - email validator function with same rules

**Patterns to reuse:**
- Lines 9-36: Docstring format with examples
- Lines 42-70: Validation order (cheap checks first)
- Lines 64-66: Local part leading/trailing dot checks pattern
- Lines 68-70: Domain part leading/trailing dot checks pattern

**Key learnings:**
1. The junior implementation uses `re` module (regex) - **BUT our task EXPLICITLY FORBIDS regex**
2. Pattern: isinstance check first (line 38-39)
3. Pattern: count('@') != 1 check early (line 42-43)
4. Pattern: split('@') for local/domain separation (line 46)
5. Pattern: length validation with chained comparison `1 <= len(x) <= 64` (lines 49, 53)
6. Lines 82-88: Domain label hyphen validation (start/end) - NOT in our spec, skip this

**Critical difference:** Our task MUST use string methods instead of regex:
- Replace `local_pattern.fullmatch(local)` with `all(c in LOCAL_ALLOWED for c in local)`
- Replace `domain_pattern.fullmatch(domain)` with `all(c in DOMAIN_ALLOWED for c in domain)`

### 2. Junior Test Suite - `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/junior/t1_email_validator/test_email_validator.py`

**Why similar:** Complete pytest test suite for same task

**Patterns to reuse:**
- Lines 7-54: `TestValidEmails` class structure with parametrize
- Lines 56-113: `TestInvalidEmails` class structure
- Lines 115-132: `TestAtSymbol` class - specific rule tests
- Lines 134-155: Length boundary tests
- Lines 242-271: Allowed characters parametrized tests
- Lines 273-334: Disallowed characters parametrized tests

**Key learnings:**
1. Use `pytest.mark.parametrize` for multiple similar test cases
2. Use descriptive `ids=` parameter for test identification
3. Group tests by validation category (structure, dots, length, characters)
4. Use `is True` / `is False` assertions (not just truthy)
5. Include type handling tests (None, int, list, dict) - lines 384-401
6. Include edge cases (whitespace, unicode, tabs, newlines) - lines 404-429

---

## Reusable Components (USE THESE, DON'T RECREATE)

### None found in codebase
This is a standalone greenfield project. No existing utilities to reuse.

**Character sets to define (from PROMPT.md lines 68-71):**
```python
LOCAL_ALLOWED = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._%-+")
DOMAIN_ALLOWED = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-")
```

---

## Codebase Conventions Discovered

### File Organization
- Pattern: Single module file with docstring header
- Example: `junior/t1_email_validator/email_validator.py:1-5`

### Naming Conventions
- Files: `snake_case.py`
- Functions: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Discovered from: `junior/t1_email_validator/email_validator.py`

### Error Handling Pattern
No exceptions - pure boolean return. From spec:
```python
# Just return False for any invalid case
return False
```

### Testing Pattern
```python
# Pattern from junior/t1_email_validator/test_email_validator.py:7-54
class TestValidEmails:
    """Tests for emails that should be valid."""

    @pytest.mark.parametrize(
        "email",
        ["user@example.com", ...],
        ids=["basic_email", ...],
    )
    def test_valid_email_formats(self, email: str) -> None:
        assert validate_email(email) is True
```

---

## Integration & Impact Analysis

### Functions/Classes/Components Being Modified:
1. **`validate_email`** in `email_validator.py` (NEW)
   - **Called by:** TASK2 test file (`test_email_validator.py`)
   - **Parameter contract:** `def validate_email(email: str) -> bool`
   - **Impact:** Foundation for test suite
   - **Breaking changes:** N/A - new file

### API/Database/External Integration:
N/A - standalone module with no external dependencies

---

## Test Strategy Discovered

### Testing Framework
- **Framework:** pytest
- **Test command:** `uv run pytest test_email_validator.py -v`
- **Config:** None specific (uses defaults)

### Test Patterns Found
- **Test file location:** Same directory as source
- **Test structure:** Classes grouping related tests, parametrized methods
- **Example from:** `junior/t1_email_validator/test_email_validator.py`

### Mocking Approach
N/A - no mocking needed for pure function

---

## Risks & Challenges Identified

### Technical Risks
1. **Character set completeness**
   - Impact: Medium - wrong characters = test failures
   - Mitigation: Use exact sets from PROMPT.md lines 68-71

### Complexity Assessment
- Overall: **Low**
- Reasoning: Pure function, well-defined rules, no dependencies

### Missing Information
- [ ] None - spec is complete and unambiguous

---

## Execution Strategy Recommendation

**Based on research findings, execute in this order:**

1. **Create `email_validator.py`** - Single function implementation
   - Read: `junior/t1_email_validator/email_validator.py:9-70` for structure
   - Create: `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/email_validator.py`
   - Follow pattern from PROMPT.md (no regex, use string methods)
   - Define LOCAL_ALLOWED and DOMAIN_ALLOWED as module-level sets
   - Implement validation in order specified in TODO.md

2. **Lint check**
   - Run: `uv run ruff check email_validator.py`
   - Run: `uv run ruff format --check email_validator.py`

3. **Manual verification**
   - Run: `uv run python -c "from email_validator import validate_email; print(validate_email('user@example.com')); print(validate_email('invalid'))"`
   - Acceptance: First returns True, second returns False

---

**Research completed:** 2025-11-30
**Total similar components found:** 2 (junior implementation + test suite)
**Total reusable components identified:** 0 (greenfield project)
**Estimated complexity:** Low
