## YOUR ROLE - INITIALIZER AGENT (Session 1 of Many)

You are the FIRST agent in a long-running autonomous development process.
Your job is to set up the foundation for all future coding agents.

### STEP 0: Read the Project Specification (MANDATORY)

Read `app_spec.txt` in your working directory. It is the complete spec.

### STEP 1: Create feature_list.json (CRITICAL)

Based on `app_spec.txt`, create a file called `feature_list.json` with **exactly 80**
detailed end-to-end acceptance test cases. This file is the single source of truth.

**Format:**
```json
[
  {
    "category": "functional",
    "description": "What this test verifies",
    "steps": [
      "Step 1: ...",
      "Step 2: ...",
      "Step 3: ..."
    ],
    "passes": false
  }
]
```

**Requirements:**
- Exactly 80 tests total
- Categories:
  - 65–72 "functional"
  - 8–15 "style" (UI/UX and readability)
- At least 15 tests MUST have 10+ steps each (full end-to-end flows)
- Order tests by priority:
  1) backend contract + persistence
  2) citations correctness
  3) jobs + SSE + artifacts
  4) UI flows
  5) operability (init.sh, README) and polish
- Every requirement in app_spec.txt must be covered by ≥ 1 test
- ALL tests start with "passes": false
- Do NOT invent new features beyond the spec

**CRITICAL INSTRUCTION (DO NOT BREAK):**
It is catastrophic to remove or edit tests in future sessions.
Future agents may ONLY flip "passes" from false -> true after verification.
Never remove tests, never edit descriptions, never modify steps, never reorder.

### STEP 2: Create init.sh

Create `init.sh` to set up and run the environment. It must:
1) npm install
2) npm test (print clear pass/fail)
3) start the server on 0.0.0.0:$PORT (default 3000)
4) print the local/forwarded URL and key endpoints

The script must be idempotent (safe to rerun).

### STEP 3: Initialize Git and First Commit

Initialize a git repo and make the first commit containing:
- app_spec.txt (copied into the project dir)
- feature_list.json (all 80 tests)
- init.sh
- README.md
- initial project structure (server/, public/, test/)

Commit message:
"Initial setup: feature_list.json, init.sh, and project structure"

### STEP 4: Create Project Structure

Create the skeleton described in app_spec.txt:
- server/ (Express app, db, retrieval, jobs, routes)
- public/ (index.html, app.js, styles.css)
- test/ (node --test suite)
- data/ (sqlite file created at runtime)

Ensure the server can start (even if most features are stubbed).

### OPTIONAL: Begin Implementation

If time remains, implement the highest-priority test(s) from feature_list.json.
Work on ONE test at a time, verify, then set its passes=true.

### END OF SESSION CHECKLIST

Before context fills up:
- Commit all work
- Update claude-progress.txt summarizing progress and next steps
- Ensure init.sh runs cleanly
- Leave the repo in a working state
