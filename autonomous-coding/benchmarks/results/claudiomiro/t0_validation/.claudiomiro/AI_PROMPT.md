# AI_PROMPT.md — T0 Validation Test

## 1. 🎯 Purpose

**What:** Create a minimal Python CLI script that outputs a JSON status message to stdout.

**Why:** This is a T0 validation/sanity check test. It verifies that the autonomous coding agent pipeline works correctly with the simplest possible task before attempting more complex work.

**Success Definition:** Running `python hello.py` produces valid JSON output with `status: "ok"` and a greeting message containing the tool name.

---

## 2. 📁 Environment & Codebase Context

**Tech Stack:**
- Python 3.11+ (standard library only)
- No external dependencies required
- No package manager setup needed

**Project Structure:**
```
/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t0_validation/
├── .claudiomiro/          # Agent metadata directory (do not modify)
│   ├── AI_PROMPT.md       # This file
│   └── ...
└── hello.py               # ← FILE TO CREATE
```

**Architecture Pattern:** Single-file CLI script. No architecture needed.

**Key Constraints:**
- Use ONLY Python standard library
- Single file output
- No virtual environment setup required
- Script must be executable directly with `python hello.py`

**Current State:** Empty project directory. The `hello.py` file does not exist yet.

---

## 3. 🧩 Related Code Context

**No related code exists** — this is a greenfield single-file task.

**Standard Library Reference:**
```python
import json
# Use json.dumps() for JSON serialization
# Print result to stdout
```

**Output Format Pattern:**
```json
{"status": "ok", "message": "Hello from <tool_name>"}
```

Where `<tool_name>` should be replaced with the actual tool/agent name (e.g., "Claude Code", "claudiomiro", or similar identifier).

---

## 4. ✅ Acceptance Criteria

**Functional Requirements:**
- [ ] File `hello.py` exists at project root
- [ ] Running `python hello.py` completes without errors (exit code 0)
- [ ] Output is valid JSON (parseable by `json.loads()`)
- [ ] JSON contains key `"status"` with value `"ok"`
- [ ] JSON contains key `"message"` with a string value starting with `"Hello from "`
- [ ] Output goes to stdout (not stderr)
- [ ] No extra output (no debug prints, no blank lines before/after)

**Technical Constraints:**
- [ ] No external dependencies (only Python standard library)
- [ ] Python 3.11+ compatible syntax
- [ ] Single file solution

**Verification Command:**
```bash
python hello.py | python -c "import json,sys; d=json.load(sys.stdin); assert d['status']=='ok'; assert d['message'].startswith('Hello from '); print('PASS')"
```

---

## 5. ⚙️ Implementation Guidance

**Execution Layers:**
- **Layer 0 (foundation):** Create `hello.py` with JSON output logic
- **No other layers** — this is a single-step task

**Implementation Steps:**
1. Create file `hello.py` at `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t0_validation/hello.py`
2. Import `json` module
3. Create dictionary with `status` and `message` keys
4. Print JSON-encoded output to stdout
5. Verify by running the script

**Expected Artifacts:**
- `hello.py` — single Python file

**Constraints:**
- Do NOT create additional files
- Do NOT add shebang line (optional, not required)
- Do NOT add type hints (unnecessary for this scope)
- Do NOT add docstrings (unnecessary for this scope)
- Do NOT create tests (explicitly not required for T0 validation)
- Do NOT create README or documentation

**Tool Name Selection:**
Use `"Claude Code"` or the agent's identifier as the tool name in the message. If uncertain, `"Claude Code"` is acceptable.

---

## 5.1 Testing Guidance

**No automated tests required.**

This is a T0 validation test — the test IS running the script and verifying the output manually or via the verification command.

**Manual Verification:**
```bash
cd /Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t0_validation
python hello.py
```

Expected output (exact format):
```json
{"status": "ok", "message": "Hello from Claude Code"}
```

---

## 6. 🔍 Verification and Traceability

**Requirements Traceability:**

| User Requirement | Acceptance Criterion |
|-----------------|---------------------|
| Script: `hello.py` | File exists at project root |
| Run: `python hello.py` | Executes without error |
| Output valid JSON | Parseable by `json.loads()` |
| Status "ok" | `status` key equals `"ok"` |
| Message with tool name | `message` starts with `"Hello from "` |
| No dependencies | Only standard library imports |

**Self-Verification Checklist:**
- [ ] Created exactly one file (`hello.py`)
- [ ] Script runs with `python hello.py`
- [ ] Output is single-line valid JSON
- [ ] JSON has correct structure
- [ ] No errors or warnings produced

---

## 7. 🧠 Reasoning Boundaries

**Keep It Simple:**
- This is intentionally minimal — resist the urge to add features
- No error handling needed (no inputs to validate)
- No edge cases exist (deterministic output)
- No abstractions needed (direct print statement)

**Decision Made:**
- Tool name: Use `"Claude Code"` unless agent has a different self-identifier

**Reference Implementation:**
```python
import json

print(json.dumps({"status": "ok", "message": "Hello from Claude Code"}))
```

This is the entire solution. Do not overcomplicate.

---

## Summary

Create `/Users/administrator/projects/claude-quickstarts/autonomous-coding/benchmarks/results/claudiomiro/t0_validation/hello.py` that prints `{"status": "ok", "message": "Hello from Claude Code"}` when executed. Verify it works. Done.
