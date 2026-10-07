## PROMPT
Perform final validation and verification of the email validator implementation. Run all tests, verify linting passes, and confirm all requirements from AI_PROMPT.md are satisfied.

**Verification Steps:**

1. **Check files exist:**
   ```bash
   ls -la email_validator.py test_email_validator.py
   ```

2. **Run all tests:**
   ```bash
   uv run pytest test_email_validator.py -v
   ```
   Expected: All tests pass (0 failures)

3. **Run linting:**
   ```bash
   uv run ruff check .
   ```
   Expected: No errors

4. **Check formatting:**
   ```bash
   uv run ruff format --check .
   ```
   Expected: No issues

5. **Manual smoke test:**
   ```bash
   uv run python -c "from email_validator import validate_email; print('Valid:', validate_email('user@example.com')); print('Invalid:', validate_email('invalid'))"
   ```
   Expected: `Valid: True` and `Invalid: False`

6. **Cross-check requirements from AI_PROMPT.md:**
   - Function signature: `validate_email(email: str) -> bool`
   - 8 validation rules implemented
   - 3 required valid email tests
   - 5+ required invalid email tests
   - Proper type hints
   - Docstrings present
   - No regex used
   - No external dependencies

**Report Format:**
```
## Final Validation Report

### Files
- [ ] email_validator.py exists
- [ ] test_email_validator.py exists

### Tests
- [ ] All tests pass
- Test count: X passed

### Linting
- [ ] ruff check passes
- [ ] ruff format passes

### Smoke Test
- [ ] validate_email("user@example.com") returns True
- [ ] validate_email("invalid") returns False

### Requirements Checklist
- [ ] Function signature correct
- [ ] All validation rules implemented
- [ ] Required test cases covered
- [ ] Code quality standards met

### Status: PASS / FAIL
```

## COMPLEXITY
Low

## CONTEXT REFERENCE
**For complete environment context, read:**
- `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/.claudiomiro/AI_PROMPT.md` - Contains full acceptance criteria (lines 78-115), verification checklist (lines 240-275)

**You MUST read AI_PROMPT.md before executing this task to verify all requirements.**

## TASK-SPECIFIC CONTEXT

### Files This Task Will Touch
- READ/VERIFY: `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/email_validator.py`
- READ/VERIFY: `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t1_email_validator/test_email_validator.py`

### Patterns to Follow
- Use verification commands from AI_PROMPT.md (lines 329-333)
- Check against acceptance criteria (lines 78-115)

### Integration Points
- Validates work from TASK1 and TASK2
- This is the final quality gate

## EXTRA DOCUMENTATION

**Validation Rule Checklist (from AI_PROMPT.md):**
1. Exactly one `@` symbol
2. Local part 1-64 chars
3. Domain part 1-255 chars
4. Domain has at least one dot
5. No consecutive dots
6. No leading/trailing dots in local
7. No leading/trailing dots in domain
8. Only allowed characters

**Required Test Cases (from AI_PROMPT.md):**
Valid:
- user@example.com
- user.name@domain.co.uk
- user+tag@example.org

Invalid:
- @example.com
- user@
- user@@example.com
- user@.com
- user@example..com

## LAYER
2 (Final)

## PARALLELIZATION
Parallel with: None (this is the final validation task)

## CONSTRAINTS
- IMPORTANT: Do not perform any git commit or git push.
- This task is READ-ONLY verification
- Do NOT modify any files
- If any check fails, report which requirement is not met
- Produce a clear PASS/FAIL status at the end
