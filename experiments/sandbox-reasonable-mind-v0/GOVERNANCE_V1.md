# Governance v1: Constitutional Mapping to Code

## Overview

This document maps the **Reasonable Mind Constitution (v1.3)** to the **runtime governance implementation**. The Constitution is the **analogy** - a user-facing framework that explains how the system operates. The code is the **reality** - the actual enforcement mechanisms.

Version: 1.0
Date: 2025-12-05
Status: Minimal v1 Implementation

---

## Constitutional Framework vs. Implementation

### The Constitution (Analogy)

The Constitution describes governance using a **governmental branches metaphor**:
- **Legislature** (Reasoning Branch) - Article II
- **Executive** (Execution Branch) - Article III
- **Judiciary** (Governance Branch) - Article IV
- **Citizenry** (Interface Branch) - Article V

### The Implementation (Reality)

The actual system uses a **Triadic Foundation** (Logic/AI/User):
- **Logic Layer** - Deterministic reasoning (categorical_engine, rule_engine, etc.)
- **AI Layer** - Probabilistic reasoning (debate_system, critic_system, etc.)
- **User Layer** - Human preferences and constraints
- **Synthesis Layer** - Emergent from interaction

### The Mapping

| Constitutional Branch | Triadic Components | Runtime Enforcement |
|-----------------------|--------------------|---------------------|
| **Legislature** (Reasoning) | AI Layer (debate, critic, semantic) | Not in v1 |
| **Executive** (Execution) | Synthesis + ExecutionProxy | `GovernedCodingAgent` |
| **Judiciary** (Governance) | ConstraintLoader + PlanValidator | `PlanValidator`, `ConstraintLoader` |
| **Citizenry** (Interface) | User Layer (role_system, clarification) | Not in v1 |

**v1 Focus**: We implement the **Executive** agent with **Judiciary** enforcement.

---

## Article-by-Article Implementation

### Article I — Universal Principles

#### §1.1 User Sovereignty
- **Constitution**: "The human user holds ultimate authority."
- **Code**: Not enforced in v1 (no user approval callback)
- **Future**: Add `approval_callback` to ExecutionProxy for escalated actions

#### §1.2 Persona Lock ✓ IMPLEMENTED
- **Constitution**: "An agent's branch and persona assignment are immutable after instantiation."
- **Code**: [`runtime/persona_lock.py`](runtime/persona_lock.py)
  - `PersonaContext` with `__setattr__` override prevents modification
  - Raises `PersonaLockViolation` on modification attempt
  - Identity hash verification with SHA-256
- **Usage**: `governed_agent.py:162-176` - persona is private, read-only access
- **Tests**: `tests/test_governed_agent.py:35-70` - TestPersonaLock class

#### §1.3 Separation of Powers
- **Constitution**: "No agent may hold powers from more than one branch."
- **Code**: `PersonaContext.agent_type` restricts capabilities
  - `AgentType.CODING_AGENT` → specific capability set
  - No cross-type capability escalation allowed
- **Future**: Multi-agent orchestration with branch enforcement

#### §1.4 Epistemic Integrity
- **Constitution**: "Agents must distinguish fact from inference and acknowledge uncertainty."
- **Code**: Not in v1 scope (AI layer concern)
- **Future**: `uncertainty_system.py` integration

#### §1.5 Constraint Binding ✓ IMPLEMENTED
- **Constitution**: "Every execution context must reference an active constraint profile hash."
- **Code**: [`governed_agent.py:88-106`](governed_agent.py)
  - `ExecutionContext` dataclass with `constraint_hash`
  - Every task creates context with plan_id + persona_id + constraint_hash
  - SHA-256 hash from `ConstraintLoader.load().integrity_hash`
- **Usage**: All `execute_task()` calls include constraint_hash in response
- **Tests**: `tests/test_governed_agent.py:73-118` - TestConstraintBinding class

#### §1.6 Plan-Before-Action ✓ IMPLEMENTED
- **Constitution**: "No execution without a validated plan."
- **Code**: [`governed_agent.py:278-330`](governed_agent.py)
  - `PlanValidator.validate_text()` runs before execution
  - If `ValidationResult.BLOCKED` → no execution, log V003
  - If `ValidationResult.ESCALATE` → requires approval
  - If `ValidationResult.APPROVED` → execute through proxy
- **Usage**: `execute_task()` always validates before executing
- **Tests**: `tests/test_governed_agent.py:121-170` - TestPlanBeforeAction class

#### §1.7 Minimal Authority
- **Constitution**: "Agents request only the permissions needed for the current task."
- **Code**: [`runtime/governance/coding_agent_profile.json`](runtime/governance/coding_agent_profile.json)
  - Whitelist approach: `allow` lists are minimal
  - Deny dangerous operations: `rm -rf`, `sudo`, etc.
  - Escalate non-routine: `pip install`, `git push`
- **Enforcement**: ExecutionProxy checks against profile before execution

#### §1.8 Constitutional Oversight Loop
- **Constitution**: "Plans, actions, and outputs may be critiqued, revised, and audited."
- **Code**: Partial in v1
  - Audit logging: `ExecutionProxy.get_audit_log()`
  - Violation tracking: `GovernedCodingAgent.get_violations()`
- **Future**: Full critique/revision workflow (Article VI)

#### §1.9 Branch-Specific Principles
- **Code**: Not in v1 (single agent only)
- **Future**: Each agent type has supplementary principles

---

### Article II — Legislature (Reasoning Branch)

**Status**: Not implemented in v1

**Future Mapping**:
- `debate_system.py` → Analyst and Critic roles
- `semantic_parser.py` → Intent decomposition
- `critic_system.py` → Plan critique

---

### Article III — Executive (Execution Branch) ✓ PARTIALLY IMPLEMENTED

#### §3.1 Purpose
- **Constitution**: "Implement validated plans through code generation, refactoring, and system maintenance."
- **Code**: `GovernedCodingAgent` class implements this

#### §3.2 Powers
- **Constitution**: Lists execution powers (modify code, run tests, git operations)
- **Code**:
  - File operations: `ExecutionProxy.read_file()`, `write_file()`, `delete_file()`
  - Subprocess: `ExecutionProxy.run_command()`
  - Sandbox boundary: All writes must be in `sandbox_root`

#### §3.3 Limits
- **Constitution**: "May not perform deep problem decomposition" / "Strictness B applies"
- **Code**: `ExecutionProxy` enforces Strictness B:
  - Read-only commands: allowed
  - Python tooling: allowed
  - git add/commit: requires approval
  - git push, pip install: blocked
  - Network: blocked

#### §3.4 Plan Approval ✓ IMPLEMENTED
- **Constitution**: "Auto-approved: Plans matching Judiciary whitelist criteria"
- **Code**: `PlanValidator` with governance_matrix.json
  - `allow` patterns → auto-approved
  - `deny` patterns → blocked
  - `escalate` patterns → requires approval (not hooked up in v1)

#### §3.5 Roles
- **Constitution**: Sandbox Coder, Refactor Agent, Build/Maintenance
- **Code**: Single `CODING_AGENT` persona type in v1
- **Future**: Multiple agent types with different profiles

---

### Article IV — Judiciary (Governance Branch) ✓ PARTIALLY IMPLEMENTED

#### §4.1 Purpose
- **Constitution**: "Set approval criteria, audit actions, curate policies, and enforce compliance."
- **Code**: Enforcement via `PlanValidator` + `ConstraintLoader`

#### §4.2 Powers
- **Constitution**: Define whitelist, review plans, audit, curate profiles
- **Code**:
  - Whitelist criteria: `governance_matrix.json`
  - Plan review: `PlanValidator.validate()`
  - Audit: `ExecutionProxy._log_audit()`
  - Profile curation: JSON files in `runtime/governance/`

#### §4.3 Limits
- **Constitution**: "May not modify sandbox or system environment"
- **Code**: ConstraintLoader and PlanValidator are read-only
  - Load policies but don't execute

#### §4.4 Roles
- **Code**: Implicit in components
  - Constraint Auditor → `ExecutionProxy` audit logging
  - Plan Reviewer → `PlanValidator`
  - Policy Curator → Human edits JSON files

#### §4.5 Chain-of-Thought Requirement
- **Code**: Not in v1 (no reasoning traces)
- **Future**: Log validation rationale in audit

#### §4.6 Non-Evasive Judgement
- **Constitution**: "If refusing approval, must provide concise constitutional rationale."
- **Code**: `ValidationOutcome.rationale` always provided
  - Example: "Blocked: Denied by policy: rm -rf"

---

### Article V — Citizenry (Interface Branch)

**Status**: Not implemented in v1

**Future Mapping**:
- `role_system.py` → Dialogue Orchestrator
- `clarification_system.py` → Intent Router
- User override → ExecutionProxy approval_callback

---

### Article VI — Planning, Critique & Execution Protocol ✓ MINIMAL

#### §6.1 Plan Types
- **Code**: `Plan` dataclass in plan_validator.py
  - Only "Simple" plans in v1 (task → validation → execution)
- **Future**: Standard plans with contingencies, open_questions

#### §6.2 Critique Phase
- **Code**: Not in v1
- **Future**: Legislature agents critique Executive plans

#### §6.3 Revision Phase
- **Code**: Not in v1
- **Future**: Revision counter, plan_id versioning

#### §6.4 Re-planning Triggers
- **Code**: Not in v1
- **Future**: Detect failures and trigger re-plan

#### §6.5 Execution Phase ✓ IMPLEMENTED
- **Constitution**: "Only validated plans may be executed by Executive agents"
- **Code**: `execute_task()` → validate → execute
  - All side effects through ExecutionProxy
  - All actions log plan_id, persona_id, constraint_hash

#### §6.6 Escalation
- **Code**: Partial - validation escalates but no human callback in v1
- **Future**: Wire `approval_callback` to user interface

---

### Article VII — Violations & Remedies ✓ IMPLEMENTED

#### §7.1 Violation Types
- **Constitution**: Defines V001-V006 codes
- **Code**: [`governed_agent.py:31-39`](governed_agent.py)
  - `ViolationCode` enum with all 6 codes
  - Only V003 (Execution without plan) enforced in v1

#### §7.2 Remediation
- **Code**:
  - Critical/High: Execution blocked, violation logged
  - Medium: Warning (not in v1)
- **Future**: Severity-based remediation workflows

#### §7.3 Logging Requirement ✓ IMPLEMENTED
- **Constitution**: "All violations must include: plan_id, persona_id, constraint_hash"
- **Code**: [`governed_agent.py:137-162`](governed_agent.py)
  - `Violation` dataclass includes all required fields
  - Persisted to `.violations/violations_YYYYMMDD.jsonl`

#### §7.4 Appeal
- **Code**: Not in v1
- **Future**: User can review violations and override

---

## Implementation Components

### Core Files

| File | Constitutional Role | Description |
|------|---------------------|-------------|
| `governed_agent.py` | Executive Agent | Main governed coding agent (Article III) |
| `runtime/persona_lock.py` | §1.2 Enforcement | Immutable agent identity |
| `runtime/constraint_loader.py` | §1.5 Enforcement | SHA-256 profile integrity |
| `runtime/execution_proxy.py` | §3.3 Enforcement | Strictness B execution control |
| `runtime/plan_validator.py` | §1.6 & §4.2 Enforcement | Plan validation + bypass detection |
| `runtime/governance/*.json` | Judiciary Policies | Governance matrix and profiles |

### Governance Profiles

| File | Purpose |
|------|---------|
| `governance_matrix.json` | Strictness B policy matrix (allow/deny/escalate) |
| `base_profile.json` | Restrictive defaults for all agents |
| `coding_agent_profile.json` | Extends base with coding capabilities |

### Test Coverage

| Test File | Coverage |
|-----------|----------|
| `tests/test_governed_agent.py` | §1.2, §1.5, §1.6, §7.1 enforcement |
| `tests/test_governance.py` | Runtime components (partial) |

### Demos

| Demo | Purpose |
|------|---------|
| `examples/ungoverned_demo.py` | Shows BEFORE state (no governance) |
| `examples/governed_demo.py` | Shows AFTER state (constitutional enforcement) |

---

## Governance Flow

### Task Execution Flow

```
User Task
    ↓
execute_task(task_description)
    ↓
Create ExecutionContext                    [§1.5 Constraint Binding]
    - plan_id (UUID)
    - persona_id (locked)
    - constraint_hash (SHA-256)
    ↓
PlanValidator.validate_text()             [§1.6 Plan-Before-Action]
    - Parse natural language
    - Extract actions
    - Check bypass patterns
    - Validate against governance_matrix
    ↓
ValidationResult:
    ├─ BLOCKED → Log V003 violation       [§7.1 Violations]
    ├─ ESCALATE → Return for approval     [§6.6 Escalation]
    └─ APPROVED → Execute
                    ↓
            ExecutionProxy.execute()      [Article III Powers]
                - Check file_operations policy
                - Check subprocess policy
                - Enforce sandbox boundary
                - Log audit entry
                    ↓
            Return result with metadata
                - plan_id
                - persona_id
                - constraint_hash
```

### Violation Logging Flow

```
Blocked Action
    ↓
_log_violation(code, description, plan_id)
    ↓
Create Violation record
    - code (V001-V006)
    - description
    - plan_id
    - persona_id (from locked persona)
    - constraint_hash (from loaded profile)
    - timestamp
    ↓
Append to in-memory violations list
    ↓
Write to .violations/violations_YYYYMMDD.jsonl
    - One violation per line
    - JSON format for parsing
```

---

## What's Enforced in v1

✅ **§1.2 Persona Lock**
- PersonaContext prevents modification after creation
- PersonaLockViolation raised on tampering attempts
- Identity hash verification

✅ **§1.5 Constraint Binding**
- Every execution has ExecutionContext
- All actions include plan_id + persona_id + constraint_hash
- SHA-256 integrity hashing of profiles

✅ **§1.6 Plan-Before-Action**
- PlanValidator runs before all execution
- Bypass detection with pattern matching
- Actions blocked without valid plan

✅ **§1.7 Minimal Authority**
- Whitelist approach in governance profiles
- Deny dangerous operations
- Escalate non-routine operations

✅ **§3.3 Strictness B**
- ExecutionProxy enforces policy matrix
- Read-only commands allowed
- Dangerous commands blocked
- Git/network require approval

✅ **§7.1 Violation Tracking**
- V003 (Execution without plan) logged
- Violations include required metadata
- Persisted to disk

✅ **§7.3 Logging Requirement**
- All violations include plan_id, persona_id, constraint_hash

---

## What's NOT in v1 (Future Work)

❌ **Multi-Agent Orchestration**
- Only single agent implemented
- No Legislature/Citizenry branches
- No cross-branch critique

❌ **User Approval Workflow**
- No approval_callback wired up
- Escalated actions just return "requires approval"
- No user override mechanism

❌ **Full Violation Codes**
- Only V003 enforced
- V001, V002, V004-V006 defined but not triggered

❌ **Plan Critique/Revision**
- No revision workflow
- No contingency handling
- No re-planning triggers

❌ **Epistemic Integrity**
- No uncertainty tracking in execution
- No fact vs. inference distinction

❌ **Appeals Process**
- No violation appeals
- No user review workflow

---

## Usage Examples

### Create Governed Agent

```python
from governed_agent import GovernedCodingAgent
from pathlib import Path

agent = GovernedCodingAgent.create(
    agent_id="my-coder-001",
    sandbox_root=Path("./sandbox"),
    governance_dir=Path("./runtime/governance")
)

# Agent is now locked to constraint profile
print(agent.constraint_hash)  # SHA-256 hash
```

### Execute Governed Task

```python
# Approved task
result = agent.execute_task("read file config.json")
assert result["status"] == "approved"

# Blocked task
result = agent.execute_task("delete all files")
assert result["status"] == "blocked"
assert len(agent.get_violations()) > 0
```

### Verify Governance

```python
# Check persona lock
try:
    agent.persona.agent_type = AgentType.ORCHESTRATOR
except PersonaLockViolation:
    print("✓ Persona lock enforced")

# Check audit trail
history = agent.get_execution_history()
for ctx in history:
    print(f"Plan {ctx['plan_id']}: {ctx['constraint_hash']}")
```

---

## Architecture Principles

1. **Constitution is Analogy, Code is Reality**
   - Constitutional language makes it understandable
   - Runtime enforcement makes it real

2. **Governance is Enforceable, Not Documentation**
   - PersonaLock prevents modification with exceptions
   - ExecutionProxy blocks denied operations
   - Violations are logged, not ignored

3. **Immutability Where It Matters**
   - Persona identity locked after creation
   - Constraint profiles hashed for integrity
   - Execution contexts are immutable records

4. **Audit Trail for Everything**
   - Every action logs plan_id + persona_id + constraint_hash
   - Violations persisted with full context
   - Execution history preserved

5. **Fail Secure, Not Fail Open**
   - Unknown actions → blocked or escalated
   - No approval callback → deny by default
   - Invalid plan → no execution

---

## Testing Governance

Run the test suite:

```bash
cd experiments/sandbox-reasonable-mind-v0
pytest tests/test_governed_agent.py -v
```

Run the demos:

```bash
# Show governance in action
python examples/governed_demo.py

# Show ungoverned comparison
python examples/ungoverned_demo.py
```

---

## Conclusion

This v1 implementation proves that **constitutional governance is enforceable**, not just aspirational documentation. The core principles (Persona Lock, Constraint Binding, Plan-Before-Action, Violation Tracking) are working and tested.

Future versions will add:
- Multi-agent orchestration (full branch separation)
- User approval workflows (human-in-the-loop)
- Critique/revision cycles (Article VI)
- All violation codes (V001-V006)
- Epistemic integrity tracking

The foundation is solid. Constitutional principles map to runtime enforcement. Governance works.
