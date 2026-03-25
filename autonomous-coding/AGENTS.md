# Autonomous Coding Quickstart Notes

Scope: `autonomous-coding/`

- V2 (`--mode v2`) is the default harness and should remain the primary path.
- Preserve resumability: never remove or silently reinterpret `state/run_state.json`.
- Preserve security boundaries in `client.py` + `security.py` (sandbox, allowlist, hook checks).
- Planner/Builder/Evaluator artifact contracts are schema-backed in `schemas/`; keep them deterministic.
- If adding new JSON artifacts, add a schema + unit tests.
- Keep `feature_list.json` as backlog/verification ledger; evaluator is authority for pass/fail outcomes.
- Prefer Playwright MCP for evaluator browser QA; Puppeteer remains fallback only.
