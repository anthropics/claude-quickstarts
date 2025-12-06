# Experiment: sandbox-reasonable-mind-v0

**Created:** 2025-12-05T08:40:00Z  
**Parent Branch:** sandbox/sandbox-reasonable-mind-v0 (branched from wgt-test-dev)

---

## Purpose

Safe, isolated environment for experimenting with:
- **ReasonableMindEngine** - Core reasoning orchestration
- **Agent Profiles** - Different reasoning configurations
- **Autonomous Coding Agents** - Self-directed development tasks
- **Logic Foundation** - Syllogistic reasoning, fallacy detection, inference

---

## Scope

### ✅ Allowed
- Code changes **only within this directory tree** (`experiments/sandbox-reasonable-mind-v0/`)
- Adding new modules, tests, and documentation inside the sandbox
- Refactoring copied code to experiment with new architectures
- Creating new agent profiles and reasoning strategies

### ❌ Forbidden
- Modifying files outside this folder
- Modifying core logic in the main repo (e.g., `agents/core/` at repo root)
- Introducing network calls or external dependencies without justification
- Pushing to remote without explicit human instruction

---

## Directory Structure

```
experiments/sandbox-reasonable-mind-v0/
├── .sandbox_config.yaml    # Agent constraints and metadata
├── EXPERIMENT.md           # This file
├── pinned-requirements.txt # Frozen dependencies
├── venv/                   # Isolated Python environment
├── agents/                 # Copied agent code for experimentation
│   ├── core/               # Core systems (copy)
│   ├── logic/              # Logic systems (copy)
│   ├── tests/              # Test suite (copy)
│   └── ...
├── pyproject.toml          # Project configuration (copy)
└── ...                     # Other project files (copies)
```

---

## Agent Permissions

### Agents MAY:
- ✅ Refactor, add code, and add tests inside this folder
- ✅ Create new modules and experiment with architectures
- ✅ Modify any file within `experiments/sandbox-reasonable-mind-v0/`
- ✅ Run tests and validate changes

### Agents MUST NOT:
- ❌ Modify files outside this folder
- ❌ Introduce network calls or external dependencies without justification
- ❌ Push commits to remote without explicit human instruction
- ❌ Delete or corrupt the `.sandbox_config.yaml` file

---

## Getting Started

### Activate the sandbox environment:
```bash
cd experiments/sandbox-reasonable-mind-v0
source venv/bin/activate
```

### Run tests:
```bash
pytest agents/tests/ -v
```

### Deactivate when done:
```bash
deactivate
```

---

## Termination / Merge Strategy

1. **Review**: Changes may be manually reviewed by the human maintainer
2. **Cherry-pick**: Selected changes can be ported back to main project via human-guided cherry-picks or patches
3. **Deletion**: The entire `experiments/sandbox-reasonable-mind-v0` folder can be deleted without harming the main codebase

---

## Experiment Log

| Date | Action | Notes |
|------|--------|-------|
| 2025-12-05 | Sandbox created | Initial clone from wgt-test-dev branch |

---

*This sandbox is self-contained. Experiment freely!*
