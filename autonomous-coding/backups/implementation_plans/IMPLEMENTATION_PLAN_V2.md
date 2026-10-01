# Autonomous Coding V2 Implementation Plan

## Current V1 architecture summary

The current `autonomous-coding/` quickstart uses a two-agent loop:
1. **Initializer session** creates `feature_list.json` and baseline project files.
2. **Coding session loop** repeatedly continues implementation.

Core behavior today:
- Session context is reset by instantiating a fresh SDK client each loop.
- Prompt handoff is mostly implicit and conversational (`initializer_prompt.md`, `coding_prompt.md`).
- Progress is inferred from `feature_list.json` only.
- Browser QA uses Puppeteer MCP tools directly.
- Single model configuration path (`--model`) with 4.5-era default.

## Target V2 architecture summary

Implement a production-oriented three-phase harness with explicit state and artifacts:
1. **Planner phase**
   - Inputs: app spec + backlog/feature ledger
   - Outputs: structured planning artifacts (acceptance criteria, backlog plan, architecture notes)
2. **Builder phase**
   - Inputs: planner artifacts + prior evaluator findings
   - Outputs: code changes + build report
3. **Evaluator phase**
   - Inputs: planner artifacts + builder report + current code state
   - Outputs: structured QA report + pass/fail/blocker decision

Orchestration rules:
- Fresh run vs resume detection from `state/run_state.json`.
- Planner runs when needed (fresh run / missing plan / force).
- Builder/evaluator run in bounded rounds (`--max-rounds`).
- Explicit completion criteria stored in state files.
- Resume-safe transitions with durable disk state.

## Files to add

- `autonomous-coding/orchestrator.py`
- `autonomous-coding/planner.py`
- `autonomous-coding/builder.py`
- `autonomous-coding/evaluator.py`
- `autonomous-coding/artifacts.py`
- `autonomous-coding/state_models.py`
- `autonomous-coding/schemas/*.json` (artifact/state schemas)
- `autonomous-coding/prompts/planner_prompt.md`
- `autonomous-coding/prompts/builder_prompt.md`
- `autonomous-coding/prompts/evaluator_prompt.md`
- `autonomous-coding/AGENTS.md`
- `autonomous-coding/tests/*` (unit + deterministic integration tests)

## Files to modify

- `autonomous-coding/autonomous_agent_demo.py` (V2-first CLI, compatibility mode)
- `autonomous-coding/agent.py` (shared session runner + V1 compatibility)
- `autonomous-coding/client.py` (phase-aware models/tools, Playwright preferred/fallback)
- `autonomous-coding/security.py` (retain + strengthen validation coverage)
- `autonomous-coding/progress.py` (round/state summaries)
- `autonomous-coding/prompts.py` (phase prompt loader + compatibility loaders)
- `autonomous-coding/README.md` (full V2 rewrite)
- `autonomous-coding/requirements.txt` (testing/schema deps)

## Compatibility strategy

- Keep existing V1 loop accessible via `--mode v1` where feasible.
- Default CLI path becomes V2.
- Preserve `feature_list.json` as backlog ledger and keep evaluator as authority for pass/fail updates.
- Maintain existing security model (sandbox + permissions + bash allowlist).

## Test strategy

1. **Unit tests**
   - JSON schema validation and artifact I/O
   - run/round state transitions
   - prompt loading
   - CLI arg parsing
   - security validation behavior
2. **Deterministic integration tests with fakes**
   - first run end-to-end
   - resume flow
   - evaluator fail -> builder retry loop
   - completion flow
3. **Optional live smoke tests**
   - guarded by env var and skipped by default

## Known risks and mitigations

1. **SDK/tooling variability for browser MCPs**
   - Mitigation: provider abstraction, Playwright preferred, Puppeteer fallback.
2. **Large prompt/artifact drift**
   - Mitigation: deterministic artifact paths + schemas + explicit parser/validation.
3. **Resume corruption from interruption**
   - Mitigation: atomic writes and explicit transition checkpoints before/after each phase.
4. **Behavior regression for existing users**
   - Mitigation: keep V1 compatibility mode and document migration clearly.
