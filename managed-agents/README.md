# Managed Agents quickstarts

Projects built on [Claude Managed Agents](https://platform.claude.com/docs/en/managed-agents/overview): agents Anthropic runs for you, with server-side sessions, sandboxed tools, and an event stream your app consumes. Each quickstart is a complete, runnable app that pairs Managed Agents with a real product surface.

## Quickstarts

- **[assistant-ui/](assistant-ui/)** puts a spreadsheet analyst in a
  browser chat built entirely from assistant-ui primitives. Sessions are
  the thread list and the only state: the sidebar is `sessions.list`, an
  old chat is its event log replayed through one pure reducer, and every
  built-in tool has its own card (a terminal for `bash`, source cards for
  `web_search`, a diff for `edit`, a chart for the client-executed
  `show_chart`). Bash is `always_ask`, so each command parks the session
  and renders an inline Allow/Deny gate that survives a reload. Composer
  attachments upload to the Files API and mount into the sandbox before
  the message is sent. No third-party credentials.
- **[chat-sdk/](chat-sdk/)** puts a research analyst in a
  browser chat with Vercel's Chat SDK. Each conversation is one
  persistent session (the conversation ID is the session ID); the
  analyst researches with web search and streams the final brief
  token by token over the same held response (session `event_deltas`
  previews) while a live feed shows the tool calls. No third-party
  credentials, and the same handler moves to Slack, Teams, Discord,
  Telegram, or WhatsApp by swapping the adapter.

- **[copilot-kit-ag-ui/](copilot-kit-ag-ui/)** puts a personal
  finance assistant in a CopilotKit chat over the AG-UI protocol.
  The upstream [`@ag-ui/claude-managed-agents`](https://www.npmjs.com/package/@ag-ui/claude-managed-agents)
  adapter maps each chat thread to a managed session and streams
  replies token by token. When the agent wants to show numbers it
  calls custom tools that render as interactive charts (payoff
  timelines, growth projections, budgets) inline in the
  conversation, with sliders that recompute client-side.

- **[knowledge-wiki/](knowledge-wiki/)** distills a document corpus
  once into a knowledge wiki (a versioned memory store) using
  parallel extraction sessions, a resolve pass, and a steered
  consolidation dream (research-preview `client.beta.dreams`), then
  answers repeated analyst questions from the wiki instead of
  re-reading documents — with `[source | as-of]` provenance on every
  fact and a fraction of the per-question token cost. The worked
  example is a real M&A data room: the 2024 Squarespace / Permira
  take-private, fetched from public SEC EDGAR filings.

- **[linear/](linear/)** answers `@mentions` and assignments in
  Linear issues with a comment, over a stateless Bun webhook bridge
  on Linear's Agent Platform. The `AgentSessionEvent` creates a
  session with the Linear session and organization IDs stored in
  session `metadata`, the handler posts a "thought" inside Linear's
  10-second window, and the `session.status_idled` webhook reads that
  metadata back to post the reply. It installs through Linear OAuth
  with `actor=app`, the first workspace to install owns the bridge,
  and Stop in Linear interrupts the running session.

- **[mcp-server-typescript/](mcp-server-typescript/)** wraps the
  Sessions API as nine MCP tools, so Claude Desktop, Claude Code, or
  claude.ai can list the agents in your workspace, start sessions,
  and relay messages to them. Eight tools map 1:1 to endpoints, and
  `wait_for_idle` turns the event stream into one request/response
  call. It creates no agents of its own. The HTTP entrypoint binds
  loopback by default, and `ALLOWED_AGENT_IDS` limits which agents a
  bearer-token holder can reach.

- **[roadtrip-planner/](roadtrip-planner/)** plans national park
  road trips in a Next.js chat built directly on a session, with no
  chat framework and no database. It shows four API features on one
  screen: `event_deltas` token streaming through a thin SSE proxy,
  vault credentials injected at a header or in a JSON body with
  `injection_location`, a per-session model override with
  `agent_with_overrides`, and a `multiagent` coordinator that hands
  its draft to a reviewer agent on the same event stream.

- **[self-hosted-sandboxes/](self-hosted-sandboxes/)** runs sessions
  on hardware you control. A self-hosted environment is a work queue:
  a host process polls it with the environment key and starts one
  short-lived Docker container per claimed session. `docker/` is the
  all-CLI baseline; `docker-memory/` runs the Python SDK worker in the
  container so each session mounts a memory store at `/mnt/memory`
  and syncs it back, and keeps the environment key out of the
  containers with a per-session token.

- **[sentry/](sentry/)** runs a Sentry triage agent on a schedule
  with no host process. A deployment starts a session on a cron
  expression, the agent pulls the last 24 hours of issues with
  `sentry-cli`, and writes a severity-ranked report. The Sentry token
  lives in a vault: the sandbox holds only a placeholder, and the
  egress proxy swaps in the real token on requests to Sentry's API
  hosts and nowhere else.

- **[slack/](slack/)** answers `@mentions` in Slack with a threaded
  reply, over a stateless Bun webhook bridge. The Slack event creates
  a session with the channel and thread stored in session `metadata`,
  the handler acks inside Slack's 3-second window, and the
  `session.status_idled` webhook reads that metadata back to post the
  reply. No database and no held connection.
