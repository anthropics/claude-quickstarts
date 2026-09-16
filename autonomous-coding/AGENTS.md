# Autonomous Coding Quickstart Notes

Scope: `autonomous-coding/`

- `orchestrated` is the primary harness path (`autonomous_agent_demo.py` default mode).
- Preserve resumability semantics of `state/run_state.json`; do not silently reinterpret completed state.
- Preserve security boundaries in `client.py` + `security.py` (sandbox, allowlist, hook checks).
- Planner/Builder/Evaluator artifact contracts are schema-backed in `schemas/`; keep them deterministic.
- Sprint contracts are required artifacts (`planning/sprint_contract_round_XX.json`) and must remain schema-backed.
- If adding new JSON artifacts, add a schema + unit tests.
- Keep `feature_list.json` as backlog/verification ledger; evaluator is authority for pass/fail outcomes.
- Prefer Playwright MCP for evaluator browser QA; Puppeteer remains fallback only.
