# MCP server (TypeScript) × Claude Managed Agents

A thin [MCP](https://modelcontextprotocol.io) server that wraps the Claude [Managed Agents](https://platform.claude.com/docs/en/managed-agents/overview) Sessions API, so Claude Desktop, Claude Code, **or** claude.ai can start and chat with the agents already in your workspace as if they were tools.

```
User ─▶ Claude (Desktop, Code, or claude.ai) ─▶ MCP: send_message + wait_for_idle ─▶ session
  ▲                                                                                    │
  └────────────────────────── agent's reply ◀─── stream-to-idle ◀──────────────────────┘
```

Nine tools. Eight are 1:1 with Managed Agents endpoints, and one (`wait_for_idle`) is the SSE to request/response shim. Same handlers, two transports.

This is the remote-control shape: every agent the server's credentials can reach, driven through the raw session primitives, from TypeScript, over stdio or HTTP. The other common shape publishes one agent as a purpose-built tool, such as `ask_research_specialist`, with per-caller keys and a continuation token for turns that outlast the client's timeout. Build that one to hand a single agent to other agent platforms. Use this one to operate your own workspace from a chat window.

## Quickstart

Needs [Bun](https://bun.sh/), the [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart) 1.19 or later (`brew install anthropics/tap/ant`), and Anthropic auth: `ant auth login` once, or an API key from [platform.claude.com](https://platform.claude.com/).

```bash
cd managed-agents/mcp-server-typescript
bun install
claude "walk me through setting this up"   # reads skill.md and drives the rest
```

Claude asks which client you're targeting and follows that path:

| Client | Transport | Entrypoint |
|---|---|---|
| **Claude Desktop / Claude Code** | stdio (local process) | `src/server.ts` |
| **claude.ai** (custom connector) | Streamable HTTP (deployed URL + bearer token) | `src/server-http.ts` |

Or by hand, for the stdio path:

```bash
ant auth login            # or put ANTHROPIC_API_KEY in .env (cp .env.example .env)
printf 'CLAUDE_ENVIRONMENT_ID=%s\n' \
  "$(ant beta:environments create --transform id --raw-output < environment.yaml)" >> .env
claude mcp add managed-agents -- bun --env-file="$PWD/.env" run "$PWD/src/server.ts"
```

This quickstart creates no agents. There is no `agents/` directory and no `setup.sh`, because the server drives the agents already in your workspace. It needs one environment, which is what the second command creates from [`environment.yaml`](environment.yaml). If the workspace has no agents yet, run `./agents/setup.sh` in a sibling quickstart such as [`../slack`](../slack) or [`../chat-sdk`](../chat-sdk) first.

## Before you put it on a network

The HTTP server's bearer token lets its holder list, read, and run **every agent in the workspace** the server's Anthropic credentials belong to, and the bill goes to those credentials. Two settings narrow that, and both are in `.env.example`:

- **`ALLOWED_AGENT_IDS`**: a comma-separated list of agent IDs. When set, `list_agents` returns only those, `get_agent` and `create_session` refuse anything else, and every tool that takes a `session_id` first checks that the session belongs to one of them. Set it before you deploy.
- **`ALLOWED_HOSTS`**: the public hostname clients will use. The server binds `127.0.0.1` by default and refuses to start on another `HOST` until this is set.

See `skill.md`, "What the token can reach", for the rest.

## Tools

| Tool | Managed Agents endpoint |
|---|---|
| `list_agents` / `get_agent` | `GET /v1/agents[/{id}]` |
| `create_session` | `POST /v1/sessions` |
| `send_message` / `interrupt` | `POST /v1/sessions/{id}/events` |
| `get_session` | `GET /v1/sessions/{id}` |
| `list_events` | `GET /v1/sessions/{id}/events` |
| `archive_session` | `POST /v1/sessions/{id}/archive` |
| **`wait_for_idle`** | streams `…/events/stream` until idle, returns reply text and why the turn stopped |

## Files

| | |
|---|---|
| `environment.yaml` | The one resource this quickstart creates: the environment sessions boot from |
| `src/scope.ts` | ID validation and the `ALLOWED_AGENT_IDS` check every tool goes through |
| `src/managed-agents.ts` | Anthropic SDK calls, shared |
| `src/tools.ts` | Nine tool registrations, each declaring what it touches, shared |
| `src/server.ts` | stdio entrypoint |
| `src/server-http.ts` | HTTP entrypoint: bearer auth, Host and Origin checks, loopback by default |
| `Dockerfile` | Fly / Railway / Render / Cloud Run deploy for the HTTP path |
| `skill.md` | Mental model, setup for both clients, gotchas, debugging |

Requires `@anthropic-ai/sdk` ≥ 0.109.0. `bun.lock` is committed because the Docker build installs from it with `--frozen-lockfile`.
