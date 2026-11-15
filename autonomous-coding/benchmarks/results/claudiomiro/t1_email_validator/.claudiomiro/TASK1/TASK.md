@dependencies []
# Task: Implement Email Validator Function

## Summary
Create the `email_validator.py` module with a `validate_email(email: str) -> bool` function that validates email addresses according to 8 specific rules. This is the foundation layer - the function must exist before tests can be written.

## Context Reference
**For complete environment context, see:**
- `../AI_PROMPT.md` - Contains full tech stack (Python 3.11+, pytest, ruff, uv), project structure, coding conventions, and validation rules

**Task-Specific Context:**
- File to create: `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/email_validator.py`
- Function signature: `validate_email(email: str) -> bool`
- Must use stdlib only - no external libraries, no regex
- Follow the example pattern from AI_PROMPT.md (lines 51-62)

## Complexity
Low

## Dependencies
Depends on: None (Layer 0 - Foundation)
Blocks: TASK2
Parallel with: None

## Detailed Steps
1. Create `email_validator.py` in project root
2. Implement `validate_email(email: str) -> bool` function with docstring
3. Implement validation rules in order:
   - Check for exactly one `@` symbol
   - Split into local and domain parts
   - Check local part length (1-64 chars)
   - Check domain part length (1-255 chars)
   - Check domain contains at least one dot
   - Check no consecutive dots (`..`) anywhere
   - Check no leading dot in local part
   - Check no trailing dot in local part
   - Check no leading dot in domain part
   - Check no trailing dot in domain part
   - Check all characters are allowed:
     - Local part: `a-z`, `A-Z`, `0-9`, `.`, `_`, `%`, `+`, `-`
     - Domain part: `a-z`, `A-Z`, `0-9`, `.`, `-`

## Acceptance Criteria
- [ ] File `email_validator.py` exists in project root
- [ ] Function `validate_email(email: str) -> bool` is defined
- [ ] Function has proper type hints
- [ ] Function has docstring explaining its purpose
- [ ] All 8 validation rules are implemented
- [ ] Function returns `True` for valid emails, `False` for invalid
- [ ] No external dependencies used
- [ ] No regex used (string methods only)
- [ ] Code passes `ruff check email_validator.py`
- [ ] Code passes `ruff format --check email_validator.py`

## Code Review Checklist
- [ ] Function signature matches spec exactly
- [ ] Type hints are correct (str -> bool)
- [ ] Docstring is present and accurate
- [ ] Validation rules are in logical order
- [ ] Early returns for efficiency
- [ ] No dead code or unused variables
- [ ] Follows Python naming conventions (snake_case)
- [ ] No over-engineering (just one function)

## Reasoning Trace
The validation order is designed for efficiency - cheaper checks first:
1. `@` symbol check is O(n) but catches most invalid inputs immediately
2. Length checks are O(1) after split
3. Dot checks are simple string operations
4. Character validation is the most expensive, done last

Using string methods instead of regex keeps the code readable and avoids import overhead. The function is intentionally simple - no custom exceptions, no logging, just a bool return.
