# Autonomous Coding Harness (V3.5)

V3.5 is a production-focused autonomous coding harness aligned with Anthropic's long-running harness patterns:
- planner -> builder -> evaluator architecture,
- durable state and schema-validated artifacts,
- resumable rounds,
- strict QA gates,
- explicit sprint contracts,
- explicit proposal negotiation artifacts before round contract merge.
- best-effort token/cost observability persisted in `state/run_state.json`.

## What changed from V3.4 to V3.5

- **Best-effort token/cost telemetry integrated into run state**: each phase run appends estimated `input_tokens`, `output_tokens`, `total_tokens`, and `estimated_cost_usd` into cumulative `llm_usage` metrics in `state/run_state.json`.
- **Lightweight progress telemetry**: concise non-verbose usage lines now print both at LLM-call level and at phase-end cumulative level.
- **Resume-safe accounting**: `--resume` continues from the existing `llm_usage` counters without resetting prior totals.
- **Schema-backed run state update**: `schemas/run_state.schema.json` now validates `llm_usage` structure and per-phase totals for deterministic artifact quality.

## What changed from V3.3 to V3.4

- **Contract negotiation artifact introduced**: each round now emits `planning/sprint_contract_negotiation_round_XX.json` (schema-backed), recording `approved|changes_requested`, feedback, and approved proposal payload used for contract merge.
- **Acceptance test progression hardening**: proposed acceptance tests are now normalized, filtered against previously assigned IDs, and deduplicated before entering new sprint contracts.
- **Proposal parsing tightened**: malformed proposal bullets now generate deterministic review feedback and do not silently leak into contracts.
- **Version/log consistency cleanup**: orchestrator and prompts now use V3.4 markers for reliable operations and auditability.
- **Telemetry clarity**: metrics output now explicitly documents the token/cost instrumentation gap as an operational action item.

## What changed from V3.2 to V3.3

- **Traceability restored and versioned cleanly**: `V3_1_TRACEABILITY_MATRIX.md` was restored to its original V3.1 content, and V3.3 changes are tracked in `V3_3_TRACEABILITY_MATRIX.md`.
- **Sprint proposal path contract formalized**: proposal artifact paths are now exposed via `ArtifactPaths.sprint_proposal_md(...)` to avoid hard-coded path drift.
- **Round progression hardening**: proposed features from builder proposals are now filtered against previously attempted features before being merged into new scope.
- **Builder typing/prompt correctness fixes**: explicit `ClaudeSDKClient` import added and proposal filename instruction now uses real round numbering (no literal `XX`).
- **Proposal parser robustness**: parser resets section state on unknown markdown headers and logs when expected proposal files are missing.
- **Operator visibility improvements**: explicit warnings are now emitted for empty `work_backlog.json` and missing prior sprint contracts used for criteria deduplication.
- **Prompt/version consistency and test hardening**: planner/evaluator prompt headers now target V3.3; round-two proposal integration test now guards against duplicate scope entries.

## What changed from V3.1 to V3.2

- **Sprint contract generation is now round-aware**: larger configurable caps, dedupe, and filtering of already-attempted scope.
- **Contract negotiation input added**: builder now produces `planning/sprint_proposal_round_XX.md`, and orchestrator uses prior-round proposals when preparing the next round contract.
- **Evaluator schema-hardening**: syntactically valid but schema-invalid QA reports are auto-fallbacked to deterministic `blocked`.
- **CLI clarity improved**: `--mode v2` now prints an explicit deprecation warning before aliasing to V3.1 runtime.
- **Resume/runtime robustness improvements**: shared client is passed explicitly to run loop (no fragile closure capture).
- **Test suite strengthened**: additional regression checks for checkpoint status, CLI warning, and evaluator schema invalidity.

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

V3.5 details:
- Default scope cap is 10 (`V3_4_SPRINT_MAX_SCOPE_ITEMS`, fallback `V3_2_SPRINT_MAX_SCOPE_ITEMS`).
- Default acceptance test cap is 12 (`V3_4_SPRINT_MAX_ACCEPTANCE_TESTS`, fallback `V3_2_SPRINT_MAX_ACCEPTANCE_TESTS`).
- Negotiation turn cap is 2 (`V3_4_MAX_NEGOTIATION_TURNS`).
- Previously attempted features/criteria are filtered to reduce repetitive contracts across rounds.
- Estimated telemetry pricing can be tuned with:
  - `V3_5_EST_INPUT_USD_PER_1M`
  - `V3_5_EST_OUTPUT_USD_PER_1M`
  - `V3_5_EST_CHARS_PER_TOKEN`

## Artifact and backlog flow

Planner outputs:
- `planning/expanded_spec.md`
- `planning/architecture.md`
- `planning/acceptance_criteria.json`
- `planning/work_backlog.json`

Round outputs:
- `planning/sprint_contract_round_XX.json`
- `planning/sprint_contract_negotiation_round_XX.json`
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

- Cost/token telemetry remains best-effort (estimated from prompt/response text size) until first-class SDK usage fields are exposed by the runner interface.
- Compatibility mode with different phase models cannot preserve a single continuous session.
- Sprint contract negotiation remains lightweight (proposal artifact handoff rather than live back-and-forth turn negotiation).

## Maintainer guide

- Keep `state/run_state.json` semantics stable.
- Every new structured artifact must have a schema and tests.
- Prefer explicit failures over silent fallback success.
- Keep evaluator as the final authority on pass/fail/blocked.
