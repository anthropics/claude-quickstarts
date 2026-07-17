## PROMPT
Create the `email_validator.py` module with a `validate_email(email: str) -> bool` function that validates email addresses according to the specified rules. Use only Python stdlib - no external libraries and no regex.

**Validation Rules to Implement (in order):**
1. Exactly one `@` symbol required
2. Split into local part (before @) and domain part (after @)
3. Local part must be 1-64 characters
4. Domain part must be 1-255 characters
5. Domain must contain at least one dot (`.`)
6. No consecutive dots (`..`) anywhere in the email
7. No leading dot in local part (e.g., `.user@example.com` → invalid)
8. No trailing dot in local part (e.g., `user.@example.com` → invalid)
9. No leading dot in domain part (e.g., `user@.example.com` → invalid)
10. No trailing dot in domain part (e.g., `user@example.com.` → invalid)
11. Only allowed characters:
    - Local part: `a-z`, `A-Z`, `0-9`, `.`, `_`, `%`, `+`, `-`
    - Domain part: `a-z`, `A-Z`, `0-9`, `.`, `-`

**Expected Function Signature:**
```python
def validate_email(email: str) -> bool:
    """Validate email address according to specified rules.

    Args:
        email: The email address to validate.

    Returns:
        True if valid, False otherwise.
    """
```

After implementation, verify with:
```bash
uv run ruff check email_validator.py
uv run ruff format --check email_validator.py
```

## COMPLEXITY
Low

## CONTEXT REFERENCE
**For complete environment context, read:**
- `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/.claudiomiro/AI_PROMPT.md` - Contains full tech stack, project structure, coding conventions

**You MUST read AI_PROMPT.md before executing this task to understand the environment.**

## TASK-SPECIFIC CONTEXT

### Files This Task Will Touch
- CREATE: `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/email_validator.py`

### Patterns to Follow
- Function pattern from AI_PROMPT.md (lines 51-62)
- Use string methods like `.count()`, `.startswith()`, `.endswith()`, `in` operator
- Use `str.split('@', 1)` to split on first @ only

### Integration Points
- This function will be imported by `test_email_validator.py` (TASK2)
- Must be a standalone module with no dependencies

## EXTRA DOCUMENTATION

**Allowed Characters Reference:**
- Both local and domain: `a-z`, `A-Z`, `0-9`, `.`, `-`
- Local part only: `_`, `%`, `+`

**Character Sets (for validation):**
```python
LOCAL_ALLOWED = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._%-+")
DOMAIN_ALLOWED = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-")
```

## LAYER
0

## PARALLELIZATION
Parallel with: None (this is foundation)

## CONSTRAINTS
- IMPORTANT: Do not perform any git commit or git push.
- DO NOT use regex - use string methods only
- DO NOT use external email validation libraries
- DO NOT create additional helper files
- DO NOT add features beyond specification
- Verify with ruff check and ruff format before completion
- Keep implementation simple and readable
