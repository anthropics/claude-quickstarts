## PROMPT
Perform final validation of the T0 validation test. Verify that `hello.py` was created correctly and produces the expected JSON output. This is a READ-ONLY validation task - do not modify any files.

Run these verification steps in order:

1. Check file exists:
```bash
ls -la /Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t0_validation/hello.py
```

2. Run the script and capture output:
```bash
cd /Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t0_validation && python hello.py
```

3. Run the full verification command:
```bash
cd /Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t0_validation && python hello.py | python -c "import json,sys; d=json.load(sys.stdin); assert d['status']=='ok'; assert d['message'].startswith('Hello from '); print('PASS')"
```

4. Verify no extra files were created:
```bash
ls -la /Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t0_validation/*.py
```

Report the final status: PASS if all checks succeed, FAIL with details if any check fails.

## COMPLEXITY
Low

## CONTEXT REFERENCE
**For complete environment context, read:**
- `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t0_validation/.claudiomiro/AI_PROMPT.md` - Contains full acceptance criteria and verification commands

**You MUST read AI_PROMPT.md before executing this task to understand the expected outcomes.**

## TASK-SPECIFIC CONTEXT

### Files This Task Will Touch
- READ ONLY: `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t0_validation/hello.py`

### Patterns to Follow
- Use verification command from AI_PROMPT.md section 4
- Follow self-verification checklist from AI_PROMPT.md section 6

### Integration Points
- Depends on TASK1 completing successfully
- This is the final validation gate for the entire T0 test

## EXTRA DOCUMENTATION
**Expected Output from hello.py:**
```json
{"status": "ok", "message": "Hello from Claude Code"}
```

**Full Verification Command:**
```bash
python hello.py | python -c "import json,sys; d=json.load(sys.stdin); assert d['status']=='ok'; assert d['message'].startswith('Hello from '); print('PASS')"
```

**Self-Verification Checklist (from AI_PROMPT.md):**
- Created exactly one file (`hello.py`)
- Script runs with `python hello.py`
- Output is single-line valid JSON
- JSON has correct structure
- No errors or warnings produced

## LAYER
Ω (Final)

## PARALLELIZATION
Parallel with: []

## CONSTRAINTS
- IMPORTANT: Do not perform any git commit or git push.
- This is a READ-ONLY validation task - do NOT modify any files
- Do NOT create any new files
- All verification must be done via CLI commands
- Must report clear PASS/FAIL status with details
- If any check fails, report which specific requirement was not met
