## PROMPT
Create a minimal Python CLI script `hello.py` that prints a JSON status message to stdout. The script must output exactly: `{"status": "ok", "message": "Hello from Claude Code"}` and use only Python standard library.

Create the file at:
`/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t0_validation/hello.py`

Implementation:
```python
import json

print(json.dumps({"status": "ok", "message": "Hello from Claude Code"}))
```

After creating the file, verify it works by running:
```bash
python /Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t0_validation/hello.py
```

## COMPLEXITY
Low

## CONTEXT REFERENCE
**For complete environment context, read:**
- `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t0_validation/.claudiomiro/AI_PROMPT.md` - Contains full tech stack, project structure, coding conventions, and reference implementation

**You MUST read AI_PROMPT.md before executing this task to understand the environment.**

## TASK-SPECIFIC CONTEXT

### Files This Task Will Touch
- CREATE: `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t0_validation/hello.py` (new file, ~3 lines)

### Patterns to Follow
- Use `json.dumps()` for JSON serialization
- Output format: `{"status": "ok", "message": "Hello from Claude Code"}`
- See reference implementation in AI_PROMPT.md section 7

### Integration Points
- This is a standalone script with no integration dependencies
- Output must be parseable by any JSON parser

## EXTRA DOCUMENTATION
**Output Format:**
```json
{"status": "ok", "message": "Hello from Claude Code"}
```

**Verification Command:**
```bash
python hello.py | python -c "import json,sys; d=json.load(sys.stdin); assert d['status']=='ok'; assert d['message'].startswith('Hello from '); print('PASS')"
```

## LAYER
0

## PARALLELIZATION
Parallel with: []

## CONSTRAINTS
- IMPORTANT: Do not perform any git commit or git push.
- Use ONLY Python standard library (json module)
- Single file output only - do NOT create additional files
- Do NOT add shebang line, type hints, docstrings, tests, or README
- Script must be executable directly with `python hello.py`
- Output must go to stdout (use print())
- No extra output (no debug prints, no blank lines)
- Must include verification by running the script after creation
