# Autonomous Coding Harness (V3.1)

V3.1 is a production-focused autonomous coding harness aligned with Anthropic's long-running harness patterns:
- planner -> builder -> evaluator architecture,
- durable state and schema-validated artifacts,
- resumable rounds,
- strict QA gates,
- explicit sprint contracts.

## What changed from V2 to V3.1

- **Primary execution path is now continuous session** across planner/builder/evaluator (single SDK client session with SDK compaction).
- **Sprint contract artifacts** are generated per round and enforced by builder + evaluator.
- **Builder silent fallback removed**: empty builder output now raises explicit runtime error.
- **Resume behavior hardened**:
  - no restart on already completed run,
  - no premature round checkpoint before successful execution.
- **Robust JSON artifact handling** with deterministic fallback for malformed evaluator reports.
- **Expanded QA discipline in prompts** (preflight checks, graded criteria, hard thresholds, pass/fail/blocked semantics).

## Architecture

Core modules:
- `orchestrator.py`: round control, resume logic, model/session strategy, sprint contract creation, timings.
- `planner.py`: planning artifact enforcement.
- `builder.py`: implementation phase execution + strict non-empty output.
- `evaluator.py`: QA report ingestion with blocked fallback behavior.
- `artifacts.py`: deterministic paths, schema validation, cached schema loads.
- `state_models.py`: typed state and run status models.

## Session model strategy (continuity vs overrides)

- **Primary V3.1 path**: all phase models identical => shared continuous client session.
- **Compatibility mode**: per-phase model overrides differ => phase-scoped sessions (continuity intentionally disabled and explicitly logged).

Recommended for maximum continuity:
```bash
python autonomous-coding/autonomous_agent_demo.py --model claude-opus-4-6
```

Advanced compatibility mode:
```bash
python autonomous-coding/autonomous_agent_demo.py \
  --planner-model claude-opus-4-6 \
  --builder-model claude-opus-4-6 \
  --evaluator-model claude-sonnet-4-6
```

## Sprint contracts

For each round, orchestrator writes:
- `planning/sprint_contract_round_XX.json`

Schema-backed minimum contract:
- `round_number`
- `features_in_scope`
- `acceptance_tests[]`

Builder and evaluator prompts explicitly require using this contract as the round oracle.

## Artifact and backlog flow

Planner outputs:
- `planning/expanded_spec.md`
- `planning/architecture.md`
- `planning/acceptance_criteria.json`
- `planning/work_backlog.json`

Round outputs:
- `planning/sprint_contract_round_XX.json`
- `builder/build_report_round_XX.md`
- `qa/qa_report_round_XX.json`
- `qa/qa_report_round_XX.md`
- `state/round_state_XX.json`

Run state:
- `state/run_state.json`

## Security

Security is preserved with layered controls:
- SDK sandbox enabled.
- Explicit filesystem/tool permissions in `.claude_settings.json`.
- Bash pre-tool hook allowlist in `security.py`.
- Risky commands receive extra validation (`pkill`, `chmod`, `init.sh`).
- `pnpm` is allowlisted for modern frontend dependency workflows.

## Running

Install dependencies:
```bash
pip install -r autonomous-coding/requirements.txt
```

Set API key for live runs:
```bash
export ANTHROPIC_API_KEY='your-key'
```

Fresh run:
```bash
python autonomous-coding/autonomous_agent_demo.py --project-dir ./my_project
```

Resume run:
```bash
python autonomous-coding/autonomous_agent_demo.py --project-dir ./my_project --resume
```

If a run is already completed, `--resume` will stop with a clear message and will not silently relaunch.

## Dry-run / deterministic harness check

```bash
python autonomous-coding/autonomous_agent_demo.py --project-dir ./my_project --dry-run
```

This validates orchestration and artifact flow without calling live models.

## Troubleshooting

- Missing API key: set `ANTHROPIC_API_KEY` (except with `--dry-run`).
- Schema validation errors: inspect artifact JSON against `schemas/*.schema.json`.
- Browser QA blocked: ensure app server is reachable and MCP tooling can start.
- Resume behavior: inspect `state/run_state.json` + latest `state/round_state_XX.json`.

## Real limitations

- Cost/token telemetry is not exposed by the current runner interface; V3.1 reports phase durations and explicitly marks token/cost metrics unavailable.
- Compatibility mode with different phase models cannot preserve a single continuous session.

## Maintainer guide

- Keep `state/run_state.json` semantics stable.
- Every new structured artifact must have a schema and tests.
- Prefer explicit failures over silent fallback success.
- Keep evaluator as the final authority on pass/fail/blocked.
