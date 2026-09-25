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

An environment and tools that Claude can use to control a desktop computer. This project demonstrates how to leverage the computer use capabilities of Claude, including support for the latest `computer_toolset_20260801` toolset shape, where each computer action is a member tool the model calls by name.

[Go to Computer Use Demo Quickstart](./computer-use-demo)

### Computer Use Best Practices

A pedagogical, native-macOS reference implementation of a computer-use agent. Unlike the containerized Computer Use Demo, this project runs directly against the macOS desktop (run it in a VM!) and demonstrates common patterns for building more reliable and cost-effective computer-use agents: explicit tool definitions, correct image sizing and pruning, prompt caching, server-side compaction, batched tool calls, a sandboxed shell, and trajectory recording. It pairs with Anthropic's [computer-use best-practices guide](https://claude.com/blog/best-practices-for-computer-and-browser-use-with-claude).

[Go to Computer Use Best Practices Quickstart](./computer-use-best-practices)

### Browser Use Demo

A complete reference implementation for browser automation powered by Claude. This project demonstrates how to give Claude the ability to navigate websites, inspect and interact with DOM elements, extract content, and fill forms using a custom Playwright-backed browser tool.

[Go to Browser Use Demo Quickstart](./browser-use-demo)

### Agents

A minimal educational implementation of LLM agents using the Claude API. The core loop is under 300 lines and demonstrates the patterns from Anthropic's [building effective agents](https://www.anthropic.com/engineering/building-effective-agents) guide, with support for both native tools and MCP server tools.

[Go to Agents Quickstart](./agents)

### Autonomous Coding Agent

An autonomous coding agent powered by the Claude Agent SDK. This project demonstrates a two-agent pattern (initializer + coding agent) that can build complete applications over multiple sessions, with progress persisted via git and a feature list that the agent works through incrementally.

[Go to Autonomous Coding Agent Quickstart](./autonomous-coding)

### Managed Agents: Chat SDK

A browser chat app powered by Claude Managed Agents and Vercel's Chat SDK. This project demonstrates how to pair a persistent Managed Agents session per conversation with a chat surface: a research analyst researches with web search and streams its brief token by token while a live feed shows the tool calls. The same handler runs on Slack, Teams, Discord, Telegram, or WhatsApp by swapping the Chat SDK adapter.

[Go to Managed Agents Chat SDK Quickstart](./managed-agents/chat-sdk)

### Managed Agents with CopilotKit and AG-UI

A personal finance assistant chat app built on a Claude Managed Agent and rendered with CopilotKit. This project demonstrates how to bridge a managed-agent session to the AG-UI protocol, stream replies token by token with event deltas, and render agent tool calls as interactive generative UI components in the chat.

[Go to Managed Agents with CopilotKit Quickstart](./managed-agents/copilot-kit-ag-ui)

### Managed Agents: Daily Brief

A scheduled agent that reads your Slack channels and GitHub pull requests each weekday and posts one short brief to Slack, built on Claude Managed Agents. This project demonstrates a deployment defined entirely as files applied with `ant apply` (agent, environment, two memory stores, vault, cron deployment), a read-only preferences store next to a read-write state store, and run steps designed to fail well unattended: per-source bookmarks, a ledger against repeats, and a source that could not be read reported as unreadable rather than as a quiet day.

[Go to Managed Agents Daily Brief Quickstart](./managed-agents/daily-brief)

### Managed Agents: Knowledge Wiki

A deal-room knowledge wiki built with Claude Managed Agents. This project demonstrates how to distill a document corpus once into a versioned memory-store knowledge wiki — using parallel extraction sessions, a resolve pass, and a steered consolidation dream — then answer repeated analyst questions from the wiki with provenance on every fact and a fraction of the per-question token cost of raw-document search. The worked example is a real M&A data room fetched from public SEC EDGAR filings.

[Go to Managed Agents Knowledge Wiki Quickstart](./managed-agents/knowledge-wiki)

### Managed Agents: Linear

An agent you can @mention or assign in Linear, backed by a Claude Managed Agent. This project demonstrates a stateless webhook bridge on Linear's Agent Platform: an `AgentSessionEvent` creates a Managed Agents session with the Linear session and organization IDs stored in session metadata, and the `session.status_idled` webhook reads that metadata back to post the reply as a comment. It installs through Linear OAuth with `actor=app`.

[Go to Managed Agents Linear Quickstart](./managed-agents/linear)

### Managed Agents: MCP Server (TypeScript)

An MCP server that exposes the Claude Managed Agents Sessions API as nine tools. This project demonstrates how to let Claude Desktop, Claude Code, or claude.ai drive the agents already in your workspace: list them, start a session, send a message, and wait for the reply, over stdio or Streamable HTTP. One tool, `wait_for_idle`, turns the session's event stream into a single request/response call, and an agent allowlist limits what a bearer-token holder can reach.

[Go to Managed Agents MCP Server (TypeScript) Quickstart](./managed-agents/mcp-server-typescript)

### Managed Agents: Road Trip Planner

A national-park road trip planner built directly on a Claude Managed Agents session, in Next.js with no chat framework and no database. This project demonstrates four API features on one screen: token-by-token streaming with `event_deltas` on the session event stream, vault credentials injected at a specific request location (`injection_location`), a per-session model override with `agent_with_overrides`, and a `multiagent` coordinator that hands its draft to a reviewer agent in a session thread.

[Go to Managed Agents Road Trip Planner Quickstart](./managed-agents/roadtrip-planner)

### Managed Agents: Sentry

A scheduled Sentry triage agent built on Claude Managed Agents. This project demonstrates a deployment that starts a session on a cron schedule with no host process, and a vault environment-variable credential that lets `sentry-cli` authenticate inside the sandbox while the real token stays outside it: the egress proxy substitutes it only on requests to Sentry's hosts.

[Go to Managed Agents Sentry Quickstart](./managed-agents/sentry)

### Managed Agents: Slack

A Slack bot backed by a Claude Managed Agent. This project demonstrates a stateless webhook bridge: an `@mention` creates a Managed Agents session with the channel and thread stored in session metadata, and the `session.status_idled` webhook reads that metadata back to post the reply in-thread. There is no database and no long-lived connection.

[Go to Managed Agents Slack Quickstart](./managed-agents/slack)

## General Usage

Each quickstart project comes with its own README and setup instructions. Generally, you'll follow these steps:

1. Clone this repository
2. Navigate to the specific quickstart directory
3. Install the required dependencies
4. Set up your Claude API key as an environment variable
5. Run the quickstart application

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
