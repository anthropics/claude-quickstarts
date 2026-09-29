# Finance assistant: Claude Managed Agents × CopilotKit

A chat app where a Claude Managed Agent acts as a personal finance assistant. Anthropic hosts the agent loop and its container, CopilotKit renders the chat, and replies stream token by token. When the agent wants to show numbers, it renders interactive charts (payoff timelines, growth projections, budget breakdowns, scenario comparisons) inline in the conversation.

The fastest way to get running, from this directory:

```sh
claude "walk me through setting up this demo"
```

Claude Code reads this project's [CLAUDE.md](CLAUDE.md) and walks you through prerequisites, provisioning, and the first conversation. Prefer to do it by hand? Read on.

## Prerequisites

- Node 22 or newer.
- The [`ant` CLI](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/quickstart) 1.30 or later (`brew install anthropics/tap/ant`), which provisions the agent.
- Anthropic API credentials with the Managed Agents beta: either `ANTHROPIC_API_KEY` exported in your shell or an `ant auth login` profile. The SDK and the CLI find both on their own.
- An org with 30-day data retention. `claude-fable-5` is not available under zero data retention.

## Commands

```sh
npm install                     # install all workspaces
ant apply agents environments   # one time: creates the environment + agent, records their IDs in claude-lock.json
npm run dev                     # dev servers: runtime on :8787, web app on :5173
```

Open http://localhost:5173 and ask:

> If I invest $500/month at a 7% annual return, what will I have in 20 years?

Follow-ups work naturally: each chat thread maps to one managed session, so the agent remembers the conversation. The server logs a Console trace URL per session so you can watch the raw agent activity side by side.

The other commands:

```sh
npm run build              # build the frontend to web/dist
npm start                  # production server: API + built frontend on one port
npm run typecheck          # typecheck both workspaces
ant apply                  # after editing agents/ or environments/: publish the change
```

[`ant apply`](https://platform.claude.com/docs/en/cli-sdks-libraries/cli/apply) creates two persistent resources from files: the agent from [`agents/financial-assistant.md`](agents/financial-assistant.md), whose frontmatter is the configuration and whose prose is the system prompt, and its container from [`environments/financial-assistant.yaml`](environments/financial-assistant.yaml). It records their IDs, and the agent's version, in `claude-lock.json`, which the server reads at boot. Agents are created once and referenced by ID on every session, so you only run it again to change the agent's definition: edit the file, run a bare `ant apply` (it reconciles every file the lockfile tracks and publishes a new version of the same agent), and restart the server, which pins sessions to the lockfile's version. This repository ignores `claude-lock.json`, since every reader creates their own resources. In a project of your own, commit it.

## Security posture

The chat endpoint has no auth, so setup provisions the agent for a small blast radius:

- The environment's container has no outbound network (`networking: limited` with an empty `allowed_hosts`). Bash and files still work for calculations. Add hosts to `allowed_hosts` in `environments/financial-assistant.yaml` if your agent needs to reach specific APIs.
- `web_fetch` is disabled. Fetching arbitrary URLs is the classic path for injected instructions to reach the model, and the tool has no domain allowlist. `web_search` stays on for current rates and limits.
- The deployed runtime spends your API credits on every message. Set `ALLOWED_ORIGINS`, keep the URL private, or put auth in front before sharing it.

## Configuration

Everything is environment variables. Copy `.env.example` to `.env` for local overrides.

| Variable | Where | Default | What it does |
| --- | --- | --- | --- |
| `ANTHROPIC_API_KEY` | server | `ant auth login` profile | API credentials |
| `ANTHROPIC_ENVIRONMENT_ID` | server | read from `claude-lock.json` | Environment ID for platforms without a persistent disk |
| `ANTHROPIC_AGENT_ID` | server | read from `claude-lock.json` | Agent ID, set together with the other two |
| `ANTHROPIC_AGENT_VERSION` | server | read from `claude-lock.json` | Agent version (integer) |
| `PORT` | server | `8787` | Runtime port |
| `ALLOWED_ORIGINS` | server | allow all | Comma-separated CORS origins |
| `VITE_COPILOT_RUNTIME_URL` | web build | `/api/copilotkit` | Runtime URL when the frontend is hosted separately |

The server prints the agent ID, version, and environment ID at startup, and they are in `claude-lock.json`, ready to paste into a deployment platform's env config. They count only when the lockfile is absent, and setting only some of them is a boot error.

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
- The deployed runtime endpoint has no auth and every message spends your API credits. See [Security posture](#security-posture).

## Architecture

The Managed Agents ↔ AG-UI translation is the upstream [`@ag-ui/claude-managed-agents`](https://www.npmjs.com/package/@ag-ui/claude-managed-agents) package: one AG-UI thread per managed session, token streaming, tool activity, interrupts, and turn time caps all live there. This repo wires that adapter into a self-hosted CopilotKit runtime and renders the visual tools.

See [CLAUDE.md](CLAUDE.md) for the architecture diagram, a map of where the interesting code is, and the design notes.
