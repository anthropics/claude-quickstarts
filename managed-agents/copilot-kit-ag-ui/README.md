# Finance assistant: Claude Managed Agents × CopilotKit

A chat app where a Claude Managed Agent acts as a personal finance assistant. Anthropic hosts the agent loop and its container, CopilotKit renders the chat, and replies stream token by token. When the agent wants to show numbers, it renders interactive charts (payoff timelines, growth projections, budget breakdowns, scenario comparisons) inline in the conversation.

The fastest way to get running, from this directory:

```sh
claude "walk me through setting up this demo"
```

Claude Code reads this project's [CLAUDE.md](CLAUDE.md) and walks you through prerequisites, provisioning, and the first conversation. Prefer to do it by hand? Read on.

## Prerequisites

- Node 22 or newer.
- Anthropic API credentials with the Managed Agents beta: either `ANTHROPIC_API_KEY` or an `ant auth login` profile. The SDK finds both on its own.
- An org with 30-day data retention. `claude-fable-5` is not available under zero data retention.

## Commands

```sh
npm install        # install all workspaces
npm run setup      # one time: provision the environment + agent
npm run dev        # dev servers: runtime on :8787, web app on :5173
```

Open http://localhost:5173 and ask:

> If I invest $500/month at a 7% annual return, what will I have in 20 years?

Follow-ups work naturally: each chat thread maps to one managed session, so the agent remembers the conversation. The server logs a Console trace URL per session so you can watch the raw agent activity side by side.

The other commands:

```sh
npm run build              # build the frontend to web/dist
npm start                  # production server: API + built frontend on one port
npm run typecheck          # typecheck both workspaces
npm run setup -- --force   # re-provision the agent from scratch
```

`npm run setup` creates two persistent resources (a cloud environment and the agent) and stores their IDs in `agent-ids.json`. Agents are created once and referenced by ID on every session, so you only run setup again to change the agent's definition.

## Configuration

Everything is environment variables. Copy `.env.example` to `.env` for local overrides.

| Variable | Where | Default | What it does |
| --- | --- | --- | --- |
| `ANTHROPIC_API_KEY` | server | `ant auth login` profile | API credentials |
| `ANTHROPIC_ENVIRONMENT_ID` | server | read from `agent-ids.json` | Environment ID for platforms without a persistent disk |
| `ANTHROPIC_AGENT_ID` | server | read from `agent-ids.json` | Agent ID, set together with the other two |
| `ANTHROPIC_AGENT_VERSION` | server | read from `agent-ids.json` | Agent version (integer) |
| `PORT` | server | `8787` | Runtime port |
| `ALLOWED_ORIGINS` | server | allow all | Comma-separated CORS origins |
| `VITE_COPILOT_RUNTIME_URL` | web build | `/api/copilotkit` | Runtime URL when the frontend is hosted separately |

`npm run setup` prints the three `ANTHROPIC_*` ID values when it finishes (re-run it any time to print them again), ready to paste into a deployment platform's env config. When all three are set they take precedence over `agent-ids.json`, and setting only some of them is a boot error.

## Deployment

The app is two pieces: a static frontend (`web/dist`) and a Node server that streams SSE. Deploy them together or apart.

**Single process** (Railway, Render, Fly.io, a VPS, any Docker host):

```sh
npm install && npm run build && npm start
```

One port serves both the API and the built frontend. Set `ANTHROPIC_API_KEY` and the three agent ID variables.

**Split** (frontend on Vercel, Netlify, or Cloudflare Pages, server on any Node host):

1. Build the frontend with `VITE_COPILOT_RUNTIME_URL` pointing at your server's `/api/copilotkit` and deploy `web/dist` as a static site.
2. Run the server with `ALLOWED_ORIGINS` set to the frontend's origin.

Platform notes:

- A single agent turn can run for minutes (the agent runs bash and web searches in its workspace) and the reply streams over SSE. On serverless platforms, raise the function's max duration. The server caps each turn at 5 minutes. Platforms that buffer responses or cap requests at a few seconds can host the frontend, not the runtime.
- The server keeps the thread-to-session map in memory. Every restart or serverless cold start starts fresh sessions. Fine for a demo, not for production.
- Cloudflare Workers does not run this Express server. Host the frontend on Cloudflare Pages and the server on a Node platform.
- The deployed runtime endpoint has no auth and every message spends your API credits. Set `ALLOWED_ORIGINS`, keep the URL private, or put auth in front before sharing it.

## Architecture

See [CLAUDE.md](CLAUDE.md) for the architecture diagram, a map of where the interesting code is, and the design notes.
