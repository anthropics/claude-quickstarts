# How the Autonomous Coding Agent Harness Works

A complete guide to understanding the architecture, execution flow, and usage patterns.

---

## Table of Contents

1. [Complete Execution Flow (Step-by-Step)](#1-complete-execution-flow)
2. [Harness vs Agent-Generated Artifacts](#2-harness-vs-agent-generated-artifacts)
3. [Two-Agent Pattern in Practice](#3-two-agent-pattern-in-practice)
4. [How to Interact With It](#4-how-to-interact-with-it)
5. [Key Files and Their Roles](#5-key-files-and-their-roles)

---

## 1. Complete Execution Flow

### When You Run: `python autonomous_agent_demo.py --project-dir ./my_app`

Here's **exactly** what happens, in order:

```
┌─────────────────────────────────────────────────────────────┐
│ PHASE 0: STARTUP AND VALIDATION                             │
└─────────────────────────────────────────────────────────────┘
```

**Step 0.1: Entry Point** (`autonomous_agent_demo.py:116`)
```python
main()
  ↓
  Parse command line arguments
  ↓
  Check ANTHROPIC_API_KEY exists
  ↓
  Normalize project_dir path (prepend generations/ if relative)
  ↓
  Call run_autonomous_agent(project_dir, model, max_iterations)
```

**Step 0.2: Project Detection** (`agent.py:122-141`)
```python
Create project_dir if it doesn't exist
  ↓
Check if feature_list.json exists
  ├─ YES → is_first_run = False (CONTINUATION mode)
  └─ NO  → is_first_run = True  (INITIALIZATION mode)
  ↓
If first run: Copy app_spec.txt to project directory
```

```
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: SESSION LOOP BEGINS (Iteration 1)                  │
└─────────────────────────────────────────────────────────────┘
```

**Step 1.1: Create Fresh Client** (`agent.py:159`)
```python
client = create_client(project_dir, model)
```

This does:
- Creates `.claude_settings.json` with security rules
- Configures sandbox (bash isolation)
- Sets up file permissions (restricted to project_dir)
- Registers security hooks (bash command allowlist)
- Configures MCP servers (puppeteer for browser automation)
- Sets working directory to project_dir

**Step 1.2: Choose Prompt** (`agent.py:161-166`)
```python
if is_first_run:
    prompt = get_initializer_prompt()  # prompts/initializer_prompt.md
else:
    prompt = get_coding_prompt()       # prompts/coding_prompt.md
```

**Step 1.3: Run Agent Session** (`agent.py:169-170`)
```python
async with client:
    status, response = await run_agent_session(client, prompt, project_dir)
```

This sends the prompt to Claude and starts the autonomous loop.

```
┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: AGENT EXECUTION (First Run - Initializer)          │
└─────────────────────────────────────────────────────────────┘
```

**What the Initializer Agent Does:**

```
Agent receives prompt: "You are the FIRST agent... Read app_spec.txt..."
  ↓
[Tool: Read] app_spec.txt
  ↓
Agent understands the project requirements
  ↓
[Tool: Write] feature_list.json
  └─ Creates 200 detailed test cases
  └─ Each has: category, description, steps[], passes: false
  └─ THIS TAKES 5-15 MINUTES (agent is writing detailed features)
  ↓
[Tool: Write] init.sh
  └─ Setup script for running the project
  ↓
[Tool: Write] README.md
  └─ Project documentation
  ↓
[Tool: Bash] git init
[Tool: Bash] git add .
[Tool: Bash] git commit -m "Initial setup: feature_list.json..."
  ↓
[Tool: Write] Basic project structure (package.json, src/ dirs, etc.)
  ↓
OPTIONAL: If time remains, start implementing first features
  ↓
[Tool: Write] claude-progress.txt
  └─ "Session 1 complete. Created feature_list.json with 200 features..."
  ↓
[Tool: Bash] git commit -m "Session 1 progress"
  ↓
Session ends (context window getting full or agent completes initialization)
```

**Step 2.4: Session Cleanup** (`agent.py:172-186`)
```python
status = "continue"  # Agent wants to keep working
  ↓
Print progress summary
  ↓
Wait 3 seconds (AUTO_CONTINUE_DELAY_SECONDS)
  ↓
Increment iteration counter
  ↓
Check if max_iterations reached
  ├─ YES → Exit loop
  └─ NO  → Continue to next iteration
```

```
┌─────────────────────────────────────────────────────────────┐
│ PHASE 3: NEXT SESSION (Iteration 2 - Coding Agent)          │
└─────────────────────────────────────────────────────────────┘
```

**Step 3.1: Fresh Context Window**
```
is_first_run = False (feature_list.json exists)
  ↓
Create NEW client (completely fresh - no memory of Session 1)
  ↓
Load coding_prompt.md instead of initializer_prompt.md
```

**What the Coding Agent Does:**

```
Agent receives prompt: "You are continuing work... FRESH context window..."
  ↓
STEP 1: GET YOUR BEARINGS (from coding_prompt.md:6-31)
  ↓
[Tool: Bash] pwd
[Tool: Bash] ls -la
  └─ See: feature_list.json, init.sh, app_spec.txt, src/, etc.
  ↓
[Tool: Read] app_spec.txt
  └─ Understand what we're building
  ↓
[Tool: Read] feature_list.json
  └─ See all 200 features, check which are done
  ↓
[Tool: Read] claude-progress.txt
  └─ Read notes from previous session(s)
  ↓
[Tool: Bash] git log --oneline -20
  └─ See commit history
  ↓
[Tool: Bash] grep '"passes": false' feature_list.json | wc -l
  └─ Count remaining work (e.g., 195 features left)
  ↓
STEP 2: START SERVERS (if needed)
  ↓
[Tool: Bash] ./init.sh
  └─ Or: npm install && npm run dev (in background)
  ↓
STEP 3: VERIFICATION TEST (critical!)
  ↓
[Tool: puppeteer_navigate] http://localhost:3000
[Tool: puppeteer_screenshot] homepage.png
  └─ Verify previous work still functions
  └─ If bugs found → mark feature as "passes": false and fix
  ↓
STEP 4: CHOOSE ONE FEATURE
  ↓
[Tool: Read] feature_list.json
  └─ Find first "passes": false feature
  └─ Example: Feature #6 "User can send message and get response"
  ↓
STEP 5: IMPLEMENT THE FEATURE
  ↓
[Tool: Write] src/components/ChatInput.tsx
[Tool: Edit] src/App.tsx
[Tool: Write] server/routes/chat.js
  └─ Implement frontend + backend
  ↓
STEP 6: VERIFY WITH BROWSER AUTOMATION
  ↓
[Tool: puppeteer_navigate] http://localhost:3000
[Tool: puppeteer_click] selector="#new-chat-button"
[Tool: puppeteer_fill] selector="#message-input" value="Hello"
[Tool: puppeteer_click] selector="#send-button"
[Tool: puppeteer_screenshot] chat_working.png
  └─ VERIFY: Message sent, response received, UI looks good
  ↓
STEP 7: UPDATE feature_list.json
  ↓
[Tool: Edit] feature_list.json
  └─ Change feature #6: "passes": false → "passes": true
  └─ NEVER modify description or steps, ONLY the passes field
  ↓
STEP 8: COMMIT PROGRESS
  ↓
[Tool: Bash] git add .
[Tool: Bash] git commit -m "Implement chat messaging - verified end-to-end

- Added ChatInput component
- Added /api/chat endpoint
- Tested with browser automation
- Updated feature_list.json: marked test #6 as passing"
  ↓
STEP 9: UPDATE PROGRESS NOTES
  ↓
[Tool: Edit] claude-progress.txt
  └─ "Session 2: Completed feature #6 (chat messaging). 194 features remaining."
  ↓
STEP 10: END SESSION CLEANLY
  ↓
Check context window usage
  └─ If getting full → commit everything and end session
  └─ Otherwise → pick next feature and continue loop
  ↓
Session ends naturally or due to context limit
```

**Step 3.2: Session Cleanup and Auto-Continue**
```python
status = "continue"
  ↓
Wait 3 seconds
  ↓
Start Iteration 3 with FRESH context window
  ↓
Repeat Phase 3 indefinitely until all features pass or max_iterations reached
```

```
┌─────────────────────────────────────────────────────────────┐
│ FINAL: EXIT CONDITIONS                                       │
└─────────────────────────────────────────────────────────────┘
```

**The loop exits when:**
1. `max_iterations` reached (if specified)
2. User presses Ctrl+C
3. All 200 features marked as passing (agent job complete)
4. Fatal error occurs

---

## 2. Harness vs Agent-Generated Artifacts

### What's Already Built (The Harness)

**These files exist BEFORE you run anything:**

```
autonomous-coding/
├── autonomous_agent_demo.py    ← Entry point (YOU run this)
├── agent.py                    ← Session management logic
├── client.py                   ← SDK configuration
├── security.py                 ← Bash command allowlist
├── progress.py                 ← Helper functions for display
├── prompts.py                  ← Prompt loading utilities
├── requirements.txt            ← Python dependencies
├── test_runner.py              ← Quick test harness
├── prompts/
│   ├── app_spec.txt           ← Project specification (input)
│   ├── initializer_prompt.md  ← Instructions for Session 1
│   ├── coding_prompt.md       ← Instructions for Session 2+
│   └── minimal_test_spec.txt  ← Simple test project
└── .venv/                      ← Python virtual environment
```

**What These Do:**

| File | Purpose | Who Uses It |
|------|---------|-------------|
| `autonomous_agent_demo.py` | Entry point, parses args, runs loop | You (run it) |
| `agent.py` | Core loop: session management, auto-continue | Harness |
| `client.py` | Configures Claude SDK with security | Harness |
| `security.py` | Validates bash commands against allowlist | Harness (hook) |
| `prompts/app_spec.txt` | Describes WHAT to build | Agent reads |
| `prompts/initializer_prompt.md` | HOW to initialize project | Agent receives |
| `prompts/coding_prompt.md` | HOW to continue coding | Agent receives |

### What the Agent Creates (Generated Artifacts)

**These files are created by the agent during execution:**

```
generations/my_project/          ← Created by harness
├── .claude_settings.json       ← Created by client.py (security config)
├── app_spec.txt                ← Copied by harness from prompts/
├── feature_list.json           ← Created by AGENT (Session 1)
├── init.sh                     ← Created by AGENT (Session 1)
├── claude-progress.txt         ← Created by AGENT (each session)
├── README.md                   ← Created by AGENT (Session 1)
├── .git/                       ← Created by AGENT (git init)
│   └── commits...              ← Created by AGENT (each session)
├── package.json                ← Created by AGENT (Session 1)
├── src/                        ← Created by AGENT (Session 2+)
│   ├── App.tsx
│   ├── components/
│   └── ...
├── server/                     ← Created by AGENT (Session 2+)
│   ├── index.js
│   ├── routes/
│   └── ...
└── [everything else]           ← Created by AGENT incrementally
```

**Key Agent Artifacts:**

| Artifact | Created When | Purpose | Modified By |
|----------|--------------|---------|-------------|
| `feature_list.json` | Session 1 | Source of truth: 200 features | Agent (marks passes: true) |
| `init.sh` | Session 1 | Setup script to run project | Agent (rarely updated) |
| `claude-progress.txt` | Each session | Handoff notes between sessions | Agent (appends each session) |
| `.git/` commits | Each session | Version control, rollback | Agent (commits progress) |
| Application code | Session 2+ | The actual software | Agent (implements features) |

### Critical Distinction

```
┌──────────────────────────────────────────────────────────────┐
│ HARNESS (You maintain this)                                  │
│                                                               │
│ • Orchestration logic (when to start sessions)               │
│ • Security enforcement (what commands are safe)              │
│ • Prompt templates (instructions for agent)                  │
│ • SDK configuration (how to call Claude)                     │
│                                                               │
│ DOES NOT KNOW: What app you're building, languages, etc.     │
└──────────────────────────────────────────────────────────────┘
                              ↓
                    Creates and manages
                              ↓
┌──────────────────────────────────────────────────────────────┐
│ AGENT (Claude SDK creates this)                              │
│                                                               │
│ • Reads app_spec.txt to understand requirements              │
│ • Generates feature_list.json (work plan)                    │
│ • Writes all application code                                │
│ • Tests features with browser automation                     │
│ • Commits progress to git                                    │
│                                                               │
│ DOES NOT KNOW: It's in a loop, previous sessions existed     │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Two-Agent Pattern in Practice

The "two-agent pattern" is really **one agent with two different prompts**.

### Why Two Prompts?

**Problem:** If you give ONE prompt that says "initialize AND build the app":
- Agent creates incomplete feature_list.json (tries to start coding too soon)
- No clear handoff between setup and implementation
- Hard to resume if interrupted during initialization

**Solution:** Separate responsibilities by session type.

### Initializer Agent (Session 1 Only)

**Purpose:** Foundation setup

**Prompt:** `prompts/initializer_prompt.md`

**Key Instructions:**
```markdown
## YOUR ROLE - INITIALIZER AGENT (Session 1 of Many)

CRITICAL FIRST TASK: Create feature_list.json with 200 detailed test cases.

SECOND TASK: Create init.sh

THIRD TASK: Initialize Git

FOURTH TASK: Create Project Structure

OPTIONAL: Start Implementation (if time permits)
```

**What Makes It Different:**
- Focuses on **breadth** (create ALL features first)
- Emphasizes completeness of feature_list.json
- Sets up infrastructure (git, init.sh)
- Knows it's the FIRST agent in a series

**Output Example:**
```json
// feature_list.json (200 features)
[
  {
    "category": "functional",
    "description": "User can create a new conversation",
    "steps": [
      "1. Click 'New Chat' button in sidebar",
      "2. Verify new conversation appears",
      "3. Verify conversation is selected",
      "4. Verify chat area is empty with welcome message"
    ],
    "passes": false
  },
  // ... 199 more features
]
```

### Coding Agent (Session 2+)

**Purpose:** Incremental implementation

**Prompt:** `prompts/coding_prompt.md`

**Key Instructions:**
```markdown
## YOUR ROLE - CODING AGENT

You are continuing work on a long-running task.
This is a FRESH context window - NO memory of previous sessions.

STEP 1: GET YOUR BEARINGS (mandatory orientation)
STEP 2: START SERVERS
STEP 3: VERIFICATION TEST (test previous work still works!)
STEP 4: CHOOSE ONE FEATURE
STEP 5: IMPLEMENT THE FEATURE
STEP 6: VERIFY WITH BROWSER AUTOMATION
STEP 7: UPDATE feature_list.json (CAREFULLY!)
STEP 8: COMMIT YOUR PROGRESS
STEP 9: UPDATE PROGRESS NOTES
STEP 10: END SESSION CLEANLY
```

**What Makes It Different:**
- Focuses on **depth** (complete one feature perfectly)
- Must orient itself each session (read progress notes, git log)
- Emphasizes verification (browser testing)
- Knows it has NO memory of previous work

### How Sessions Transition

```
Session 1 (Initializer)
  ↓
  Creates feature_list.json
  Commits to git
  Writes claude-progress.txt
  ↓
  Context window fills up
  ↓
  Session ends
  ↓
  ═══════════════════════════════════
  │ 3 second delay                  │
  ═══════════════════════════════════
  ↓
Session 2 (Coding Agent) - FRESH CONTEXT
  ↓
  Detects feature_list.json exists
  Uses coding_prompt.md
  ↓
  Reads app_spec.txt (learn requirements)
  Reads feature_list.json (see work plan)
  Reads claude-progress.txt (see what was done)
  Reads git log (see commits)
  ↓
  NOW understands where to start
  ↓
  Implements Feature #1
  Marks "passes": true
  Commits
  Updates claude-progress.txt
  ↓
  Context window fills up
  ↓
  Session ends
  ↓
  ═══════════════════════════════════
  │ 3 second delay                  │
  ═══════════════════════════════════
  ↓
Session 3 (Coding Agent) - FRESH CONTEXT
  ↓
  Repeats orientation steps
  Implements Feature #2
  ...
```

### The "Stateless Handoff" Mechanism

Each coding session is completely stateless:

```python
# Session 2 agent has ZERO memory of Session 1
# How does it know what to do?

# It reads persistent artifacts:
[Tool: Read] feature_list.json        # Work plan
[Tool: Read] claude-progress.txt      # What was done
[Tool: Bash] git log                  # Implementation history
[Tool: Read] app_spec.txt             # Requirements

# These files ARE the "memory"
```

This is why the prompts emphasize:
- **NEVER remove features** from feature_list.json
- **ALWAYS commit progress** before ending
- **ALWAYS update claude-progress.txt**

---

## 4. How to Interact With It

### Before Starting

**1. Set Clear Expectations**
```bash
# Quick test (2-3 iterations)
python autonomous_agent_demo.py --max-iterations 3

# Full run (will run for hours)
python autonomous_agent_demo.py  # No limit
```

**2. Customize the Spec (Optional)**
```bash
# Edit what you want built
nano prompts/app_spec.txt

# Or use minimal test
python test_runner.py --use-minimal-spec
```

**3. Check Security Allowlist**
```bash
# Review allowed commands
grep ALLOWED_COMMANDS security.py

# Add project-specific commands if needed
# e.g., "docker", "kubectl" for containerized projects
```

### During Execution

**When to Watch:**
```
✅ Let it run (hands-off):
  • [Tool: Read] - Reading files
  • [Tool: Write] - Writing code
  • [Tool: Edit] - Modifying code
  • [Tool: Bash] - Running npm install, git commit
  • [Tool: puppeteer_*] - Testing in browser

⚠️  Monitor but don't intervene:
  • First session taking 10-20 minutes (normal for 200 features)
  • Multiple commits in sequence
  • Browser testing with screenshots

🛑 Might need intervention:
  • [BLOCKED] messages (command not in allowlist)
  • Repeated errors on same feature
  • Cost exceeding expectations
  • Agent seems stuck in loop
```

**When to Interrupt (Ctrl+C):**
- Cost concerns (check tokens used)
- Agent making mistakes repeatedly
- Want to inspect progress
- End of work day (resume tomorrow)
- Testing complete (just wanted to see it work)

**Safe to interrupt because:**
```python
# Agent commits after each feature
git log --oneline  # See all progress saved

# feature_list.json tracks completion
grep '"passes": true' feature_list.json

# Can resume from exact same spot
python autonomous_agent_demo.py  # Continues where it left off
```

### After Sessions

**Inspect Progress:**
```bash
cd generations/my_project

# See what was built
ls -la
tree -L 2

# Check completion status
jq '[.[] | select(.passes == true)] | length' feature_list.json
# Output: 12 (out of 200)

# Read handoff notes
cat claude-progress.txt
```

**Test the App:**
```bash
# Use agent-generated setup script
./init.sh

# Or manually
npm install
npm run dev

# Open browser to test
```

**Review Code Quality:**
```bash
# Check recent commits
git log --oneline -10

# Review specific implementation
git show HEAD:src/components/ChatInput.tsx

# See what changed
git diff HEAD~3..HEAD
```

**Decide Next Steps:**
```bash
# Continue for more iterations
python autonomous_agent_demo.py --max-iterations 5

# Or let it finish
python autonomous_agent_demo.py  # Unlimited

# Or make changes and restart
nano prompts/app_spec.txt  # Adjust requirements
rm -rf generations/my_project  # Start fresh
python autonomous_agent_demo.py  # New initialization
```

### When to Intervene in Code

**DON'T edit agent-generated code UNLESS:**
- Agent is fundamentally stuck (unlikely)
- You want to add custom business logic the agent can't know
- Security issue needs immediate fix

**If you DO edit:**
```bash
# Commit your changes
git add .
git commit -m "Manual fix: [what you changed]"

# Update progress notes
echo "Manual intervention: [what/why]" >> claude-progress.txt

# Then let agent continue
python autonomous_agent_demo.py
```

### Collaboration Pattern

**You provide:**
- High-level requirements (app_spec.txt)
- Feature count adjustment (200 vs 50 vs 500)
- Security boundaries (allowlist)
- When to start/stop

**Agent provides:**
- Detailed work breakdown (feature_list.json)
- Complete implementation
- Automated testing
- Git history

**You both maintain:**
- feature_list.json (agent marks passing, you might mark failing if you find bugs)
- claude-progress.txt (agent writes, you can add notes)

---

## 5. Key Files and Their Roles

### Harness Files (You Edit These)

#### `autonomous_agent_demo.py`
**Role:** Entry point and orchestrator

**What it does:**
```python
1. Parse CLI arguments (--project-dir, --max-iterations, --model)
2. Validate environment (ANTHROPIC_API_KEY)
3. Normalize paths (add generations/ prefix)
4. Call run_autonomous_agent() in agent.py
5. Handle Ctrl+C gracefully
```

**When to edit:**
- Add new CLI arguments
- Change default model
- Modify project directory structure

**Dependencies:**
- `agent.py` (calls run_autonomous_agent)

---

#### `agent.py`
**Role:** Session loop and lifecycle management

**Key Functions:**

**`run_autonomous_agent()`** (agent.py:97)
```python
Main loop:
1. Detect first run vs continuation (check feature_list.json)
2. For each iteration:
   - Create fresh client
   - Choose prompt (initializer vs coding)
   - Run session
   - Handle status (continue/error)
   - Wait 3 seconds
   - Repeat
3. Print final summary
```

**`run_agent_session()`** (agent.py:23)
```python
Single session execution:
1. Send prompt to Claude SDK
2. Stream response blocks
3. Show tool use to user
4. Return status ("continue" or "error")
```

**When to edit:**
- Change auto-continue delay (AUTO_CONTINUE_DELAY_SECONDS)
- Modify session lifecycle
- Add custom logging

**Dependencies:**
- `client.py` (creates Claude SDK client)
- `prompts.py` (loads prompts)
- `progress.py` (displays summaries)

---

#### `client.py`
**Role:** Claude SDK configuration with security

**Key Function:**

**`create_client()`** (client.py:40)
```python
Creates ClaudeSDKClient with:
1. Security settings (.claude_settings.json):
   - Sandbox enabled (bash isolation)
   - File permissions (restricted to project_dir)
   - Tool allowlist (Read, Write, Edit, Glob, Grep, Bash, MCP tools)
2. Pre-tool-use hooks:
   - bash_security_hook validates Bash commands
3. MCP servers:
   - Puppeteer for browser automation
4. System prompt:
   - "You are an expert full-stack developer..."
5. Working directory:
   - Set to project_dir
```

**Generated Files:**
- `.claude_settings.json` in project directory

**When to edit:**
- Add new MCP servers
- Modify file permissions
- Change system prompt
- Add more security hooks

**Dependencies:**
- `security.py` (bash_security_hook)

---

#### `security.py`
**Role:** Bash command validation (allowlist)

**Key Component:**

**`ALLOWED_COMMANDS`** (security.py:15)
```python
{
    "ls", "cat", "head", "tail", "wc", "grep",  # File inspection
    "cp", "mkdir", "chmod",                      # File operations
    "pwd",                                       # Directory
    "npm", "node",                               # Node.js
    "git",                                       # Version control
    "ps", "lsof", "sleep", "pkill",             # Process management
    "init.sh",                                   # Init scripts
}
```

**`bash_security_hook()`** (security.py:297)
```python
Pre-tool-use hook that:
1. Extracts commands from bash string
2. Checks each against ALLOWED_COMMANDS
3. Blocks if not allowed
4. Performs extra validation for sensitive commands:
   - pkill: only dev processes (node, npm)
   - chmod: only +x mode
   - init.sh: only ./init.sh
```

**When to edit:**
- Add commands for your project (e.g., "docker", "python")
- Adjust validation rules
- Add new sensitive commands

**Called by:**
- `client.py` (registered as PreToolUse hook)

---

#### `prompts.py`
**Role:** Load prompt templates

**Functions:**
```python
load_prompt(name)           # Load prompts/{name}.md
get_initializer_prompt()    # Load initializer_prompt.md
get_coding_prompt()         # Load coding_prompt.md
copy_spec_to_project()      # Copy app_spec.txt to project dir
```

**When to edit:**
- Add new prompt templates
- Modify prompt loading logic

---

#### `progress.py`
**Role:** Display utilities

**Functions:**
```python
print_session_header()      # Print "SESSION 1", "SESSION 2", etc.
print_progress_summary()    # Show features completed/remaining
```

**When to edit:**
- Customize progress display
- Add metrics (tokens, cost, time)

---

### Prompt Files (You Edit These for Different Projects)

#### `prompts/app_spec.txt`
**Role:** Project requirements specification

**What it contains:**
```xml
<project_specification>
  <project_name>...</project_name>
  <overview>What to build</overview>
  <technology_stack>Languages, frameworks</technology_stack>
  <core_features>Detailed feature list</core_features>
  <database_schema>DB tables</database_schema>
  <api_endpoints_summary>API routes</api_endpoints_summary>
  <ui_layout>UI structure</ui_layout>
  <design_system>Colors, typography</design_system>
  <implementation_steps>Suggested order</implementation_steps>
  <success_criteria>Definition of done</success_criteria>
</project_specification>
```

**When to edit:**
- Building a different application
- Changing tech stack
- Adjusting scope

**Read by:**
- Agent (Session 1 and all subsequent sessions)

---

#### `prompts/initializer_prompt.md`
**Role:** Instructions for Session 1 (initialization)

**Key sections:**
```markdown
1. YOUR ROLE - INITIALIZER AGENT
2. FIRST: Read the Project Specification
3. CRITICAL FIRST TASK: Create feature_list.json (200 features)
4. SECOND TASK: Create init.sh
5. THIRD TASK: Initialize Git
6. FOURTH TASK: Create Project Structure
7. OPTIONAL: Start Implementation
8. ENDING THIS SESSION
```

**When to edit:**
- Change feature count (200 → 50 or 500)
- Modify initialization steps
- Add custom setup requirements

---

#### `prompts/coding_prompt.md`
**Role:** Instructions for Session 2+ (coding)

**Key sections:**
```markdown
STEP 1: GET YOUR BEARINGS (orientation)
STEP 2: START SERVERS
STEP 3: VERIFICATION TEST (regression check)
STEP 4: CHOOSE ONE FEATURE
STEP 5: IMPLEMENT THE FEATURE
STEP 6: VERIFY WITH BROWSER AUTOMATION
STEP 7: UPDATE feature_list.json (CAREFULLY!)
STEP 8: COMMIT YOUR PROGRESS
STEP 9: UPDATE PROGRESS NOTES
STEP 10: END SESSION CLEANLY

TESTING REQUIREMENTS (browser automation)
IMPORTANT REMINDERS (quality bar)
```

**When to edit:**
- Adjust workflow steps
- Change testing requirements
- Modify quality standards

---

### Agent-Generated Files (Don't Edit These)

#### `feature_list.json`
**Created by:** Agent (Session 1)
**Modified by:** Agent (marks passes: true)
**Format:**
```json
[
  {
    "category": "functional",
    "description": "What this feature does",
    "steps": ["Step 1", "Step 2", "Step 3"],
    "passes": false  ← Agent changes to true when verified
  }
]
```

**Critical rules:**
- NEVER remove features
- NEVER edit descriptions/steps
- ONLY change "passes" field

---

#### `init.sh`
**Created by:** Agent (Session 1)
**Purpose:** One-command setup script

**Typical contents:**
```bash
#!/bin/bash
npm install
npm run dev &
echo "App running at http://localhost:3000"
```

---

#### `claude-progress.txt`
**Created by:** Agent (Session 1)
**Updated by:** Agent (each session)

**Example:**
```
Session 1: Initialized project. Created feature_list.json with 200 features.
Session 2: Completed features #1-3 (chat interface, message display). 197 remaining.
Session 3: Completed features #4-6 (streaming, markdown). 194 remaining.
```

---

#### `.claude_settings.json`
**Created by:** Harness (client.py)
**Purpose:** Security configuration

**Example:**
```json
{
  "sandbox": {
    "enabled": true,
    "autoAllowBashIfSandboxed": true
  },
  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [
      "Read(./**)",
      "Write(./**)",
      "Edit(./**)",
      "Glob(./**)",
      "Grep(./**)",
      "Bash(*)"
    ]
  }
}
```

---

## File Dependency Graph

```
autonomous_agent_demo.py
  ↓
  calls
  ↓
agent.py
  ├─→ client.py ────→ security.py (bash_security_hook)
  ├─→ prompts.py
  └─→ progress.py

prompts.py loads:
  ├─→ prompts/initializer_prompt.md
  ├─→ prompts/coding_prompt.md
  └─→ prompts/app_spec.txt

Agent reads/writes:
  ├─→ generations/my_project/feature_list.json
  ├─→ generations/my_project/claude-progress.txt
  ├─→ generations/my_project/init.sh
  └─→ generations/my_project/[application code]
```

---

## Summary

**The harness is a control loop that:**
1. Creates fresh context windows
2. Loads appropriate prompts
3. Enforces security boundaries
4. Manages auto-continuation

**The agent is Claude receiving prompts that:**
1. Read persistent artifacts (feature_list.json, git, progress notes)
2. Implement features one at a time
3. Test with browser automation
4. Commit progress for next session

**Together they create a "persistent agent" that:**
- Works across many hours
- Never loses progress
- Operates autonomously
- Leaves auditable artifacts

The key insight: **Statelessness + Persistence = Long-running autonomy**
