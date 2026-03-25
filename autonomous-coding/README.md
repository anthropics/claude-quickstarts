# Autonomous Coding Harness (V2)

V2 is a long-running, resumable autonomous coding harness with explicit phases and durable artifacts.

## What V2 is

V2 replaces the old two-agent default with a three-phase loop:
1. **Planner**: Converts spec + backlog into explicit plan artifacts.
2. **Builder**: Implements prioritized work and writes a build report.
3. **Evaluator/QA**: Verifies behavior with browser QA and writes structured findings.

The default run cycle is:
- planner pass
- builder pass
- evaluator pass
- repeat builder/evaluator up to bounded max rounds when QA finds blockers

## V1 vs V2

- **V1**: initializer + coding loop, mostly prompt-driven handoff.
- **V2**: planner/builder/evaluator with schema-validated artifact handoff and persisted run state.
- **V1 compatibility** remains available via `--mode v1`.

## Directory structure

```text
autonomous-coding/
├── autonomous_agent_demo.py
├── orchestrator.py
├── planner.py
├── builder.py
├── evaluator.py
├── artifacts.py
├── state_models.py
├── client.py
├── security.py
├── prompts.py
├── prompts/
│   ├── app_spec.txt
│   ├── planner_prompt.md
│   ├── builder_prompt.md
│   ├── evaluator_prompt.md
│   ├── initializer_prompt.md
│   └── coding_prompt.md
├── schemas/
│   ├── run_state.schema.json
│   ├── round_state.schema.json
│   ├── acceptance_criteria.schema.json
│   ├── work_backlog.schema.json
│   └── qa_report.schema.json
└── tests/
```

## Installation

```bash
pip install -r autonomous-coding/requirements.txt
npm install -g @anthropic-ai/claude-code
```

Set API key for non-dry-run execution:

```bash
export ANTHROPIC_API_KEY='your-key'
```

## Model configuration (4.6-oriented)

Defaults use `claude-sonnet-4-6` for all phases.

Override all phases at once:

```bash
python autonomous-coding/autonomous_agent_demo.py --model claude-sonnet-4-6
```

Or configure per phase:

```bash
python autonomous-coding/autonomous_agent_demo.py \
  --planner-model claude-sonnet-4-6 \
  --builder-model claude-sonnet-4-6 \
  --evaluator-model claude-sonnet-4-6
```

## Start a fresh run

```bash
python autonomous-coding/autonomous_agent_demo.py --project-dir ./my_project
```

## Resume an existing run

```bash
python autonomous-coding/autonomous_agent_demo.py --project-dir ./my_project --resume
```

## Useful flags

- `--max-rounds N`: bound builder/evaluator retry rounds.
- `--planner-only`: run planner and stop.
- `--qa-only`: run evaluator only for next round.
- `--dry-run`: deterministic non-network execution.
- `--mode v1`: run legacy two-agent flow.

## Artifact contract

Planner outputs:
- `planning/expanded_spec.md`
- `planning/architecture.md`
- `planning/acceptance_criteria.json`
- `planning/work_backlog.json`

State outputs:
- `state/run_state.json`
- `state/round_state_XX.json`

Builder outputs:
- `builder/build_report_round_XX.md`

Evaluator outputs:
- `qa/qa_report_round_XX.json`
- `qa/qa_report_round_XX.md`

All structured JSON artifacts are validated against `schemas/`.

## Browser QA

Evaluator is expected to perform browser-based QA via **Playwright MCP** (preferred). Puppeteer is retained as fallback if required by environment compatibility.

If browser QA cannot start, evaluator must emit a blocker (`result: blocked`) instead of passing.

## Security model

Defense in depth remains enabled:
- Sandbox enabled in SDK settings.
- Filesystem permissions constrained to project directory.
- Bash pre-tool hook allowlists commands and validates risky commands (`pkill`, `chmod`, `init.sh`).

## Dry-run/test mode

Use dry-run to validate orchestration and artifact generation without model/network calls:

```bash
python autonomous-coding/autonomous_agent_demo.py --project-dir ./my_project --dry-run
```

## Troubleshooting

- **Missing API key**: set `ANTHROPIC_API_KEY` unless using `--dry-run`.
- **Run appears stuck**: inspect `state/run_state.json` and latest round artifacts.
- **Schema validation failures**: inspect malformed JSON and corresponding schema in `schemas/`.
- **Browser tooling issues**: check local `npx` availability and Playwright MCP startup.

## Limitations

- V2 relies on model compliance with prompt artifact contracts.
- Browser MCP startup depends on host Node/npm environment.
- Legacy V1 prompt flow is kept only for compatibility, not as primary architecture.

## Maintainer notes

- Keep planner and evaluator first-class phases.
- Keep all important transitions represented in persisted state.
- Add tests for every new state transition and schema.
