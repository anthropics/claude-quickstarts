# Claude Quickstarts

Claude Quickstarts is a collection of projects designed to help developers quickly get started with building  applications using the Claude API. Each quickstart provides a foundation that you can easily build upon and customize for your specific needs.

## Getting Started

To use these quickstarts, you'll need an Claude API key. If you don't have one yet, you can sign up for free at [console.anthropic.com](https://console.anthropic.com).

## Available Quickstarts

### Customer Support Agent

A customer support agent powered by Claude. This project demonstrates how to leverage Claude's natural language understanding and generation capabilities to create an AI-assisted customer support system with access to a knowledge base.

[Go to Customer Support Agent Quickstart](./customer-support-agent)

### Financial Data Analyst

A financial data analyst powered by Claude. This project demonstrates how to leverage Claude's capabilities with interactive data visualization to analyze financial data via chat.

[Go to Financial Data Analyst Quickstart](./financial-data-analyst)

### Computer Use Demo

An environment and tools that Claude can use to control a desktop computer. This project demonstrates how to leverage the computer use capabilities of Claude, including support for the latest `computer_use_20251124` tool version with zoom actions.

[Go to Computer Use Demo Quickstart](./computer-use-demo)

### Autonomous Coding Agent

An autonomous coding agent powered by the Claude Agent SDK. This project demonstrates a two-agent pattern (initializer + coding agent) that can build complete applications over multiple sessions, with progress persisted via git and a feature list that the agent works through incrementally.

[Go to Autonomous Coding Agent Quickstart](./autonomous-coding)

## General Usage

Each quickstart project comes with its own README and setup instructions. Generally, you'll follow these steps:

1. Clone this repository
2. Navigate to the specific quickstart directory
3. Install the required dependencies
4. Set up your Claude API key as an environment variable
5. Run the quickstart application

## Architecture Next Steps (Roadmap)

Full improvement list (definitions preserved):
- Add a pluggable decision model with bounded utility weights and per-role profiles (researcher vs. operator).
- Require citations for score inputs; block or down-rank uncited claims; surface missing-evidence warnings.
- Add contradiction detection with policy (block vs. penalize) and show conflicts in outputs.
- Support hard/soft constraints and constraint relaxation paths; detect “no options left” and escalate or request info.
- Risk bands that trigger extra evidence or critic/debate for high-risk choices; add a safe fallback option.
- Integrate a lightweight proof/rule engine to cross-check LLM conclusions; require proof-or-flag.
- Expand inference patterns (modus tollens, syllogisms, quantifiers) with formal parsing before NL fallback.
- Improve semantic parsing: compositional parse, richer quantifiers/modalities, preserve subject/provenance, calibration for low confidence.
- Retrieval augmentation: vector + keyword + episodic memories; feed top-k into reasoning/plans; cache parses/validations.
- Memory persistence (SQLite/JSONL) with TTL and eviction; log tool outcomes and decisions for replay.
- Planner preconditions/effects with state validation; debounced rescoring when state changes; detect conflicting effects.
- Tool selection policy with scoring (fit, cost, reliability), retries, timeouts, and circuit breakers.
- Observation–action loop: execute, observe, update state, replan; not just one-shot plans.
- Critic/debate: multi-sample self-consistency, LLM critic pass, reconcile via voting/score; gate risky outputs.
- Confidence propagation: chain confidence product/log-odds; surface rationale for low/high confidence; abstain when too low.
- Hallucination guard v2: citation thresholds per claim, penalize uncited spans, and label speculative content.
- Source trust: weight facts by source reliability/recency; resolve contradictory facts using trust + confidence.
- Clarification prompts: when parses are low-confidence or constraints block all options, ask the user for specifics.
- Structured observability: JSONL traces with inputs, parses, proofs, tools, scores, gates, warnings; add a replay CLI.
- Benchmarks: small gold tasks for parsing, inference, planning success, and hallucination rate; gate CI on them.
- Deterministic tests: end-to-end scenarios with expected decisions, plus adversarial cases (contradictions, low evidence).
- Performance hygiene: cache intermediate parses/validations, limit chain depth, enforce timeouts, and budget tool calls.
- Role specialization: load per-agent profiles (weights, tools, risk tolerance, critics) at runtime.
- Plan quality scoring: evaluate expected utility vs. cost/time; prune dominated plans; prefer minimal-risk plans.
- Constraint-aware execution: precondition checks before steps; early halt on unsatisfiable plans with clear reason.
- Safety filters: PII/policy checks before emitting outputs; block unsafe tool args; sanitize tool responses.
- Failure handling: structured error taxonomy; automatic recovery steps; log failure causes for learning.
- Latency control: parallelize independent steps; batch retrieval; degrade gracefully when evidence is slow.
- UI/UX hooks: surface warnings, risk, and evidence inline for users; provide “verify” buttons to re-run critical checks.
- Calibration: periodic evaluation to adjust weights/thresholds; dampen updates (learning rates) to prevent oscillation.

Initial high-impact subset to implement first (from the list above):
1) Add a pluggable decision model with bounded utility weights and per-role profiles (researcher vs. operator).
2) Require citations for score inputs; block or down-rank uncited claims; surface missing-evidence warnings.
3) Add contradiction detection with policy (block vs. penalize) and show conflicts in outputs.
4) Support hard/soft constraints and constraint relaxation paths; detect “no options left” and escalate or request info.
5) Risk bands that trigger extra evidence or critic/debate for high-risk choices; add a safe fallback option.

### Visuals

- See `agents/ARCHITECTURE_VIEWS.md` for diagrams of the reasoning flow, decision model, planner/state loop, validation/critic/guard, and WG alignment intent.

## Explore Further

To deepen your understanding of working with Claude and the Claude API, check out these resources:

- [Claude API Documentation](https://docs.claude.com)
- [Claude Cookbooks](https://github.com/anthropics/claude-cookbooks) - A collection of code snippets and guides for common tasks
- [Claude API Fundamentals Course](https://github.com/anthropics/courses/tree/master/anthropic_api_fundamentals)

## Contributing

We welcome contributions to the Claude Quickstarts repository! If you have ideas for new quickstart projects or improvements to existing ones, please open an issue or submit a pull request.

## Community and Support

- Join our [Anthropic Discord community](https://www.anthropic.com/discord) for discussions and support
- Check out the [Anthropic support documentation](https://support.anthropic.com) for additional help

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
