# Chat SDK × Claude Managed Agents

A research analyst in a browser chat window. Vercel's [Chat SDK](https://chat-sdk.dev/) owns the chat surface. One persistent [Managed Agents](https://platform.claude.com/docs/en/managed-agents/overview) session per conversation owns the research, streaming its reply token by token while a live feed shows the tool calls it makes.

The Chat SDK is a universal chat layer: one type-safe handler, 15+ adapters, from Slack and Teams to Discord and WhatsApp. Managed Agents is the agent behind it, all server-side: the tool loop, the sandboxed web research, session state, and optional memory stores. Swapping the adapter moves the analyst to another surface. Only `src/bot.ts` changes (`skill.md`, "Two held streams").

The server stores nothing: the `useChat` conversation ID is a Managed Agents session ID. The sidebar is the sessions API. Transcripts replay from the session's event log. Compaction and prompt caching happen inside the session.

The only credential is Anthropic auth: no Meta or Slack app, no webhook, no tunnel. Design notes live in [`CLAUDE.md`](./CLAUDE.md) and [`skill.md`](./skill.md).

## Quickstart

Needs Node 22.9 or later and Anthropic auth (an API key, or `ant auth login` once).

```bash
cd managed-agents/chat-sdk
npm install
claude "walk me through setting up this demo"
```

Claude reads [`skill.md`](./skill.md) and drives the whole setup. By hand instead:

```bash
cp .env.example .env      # add ANTHROPIC_API_KEY, or skip it after `ant auth login`
npm run setup             # one-time: creates the agent + environment; paste the printed IDs into .env
npm run dev               # open http://localhost:3000 and ask for a brief on any topic
```

Token previews (`event_deltas`) are gated per organization while the 2026-07-01 Managed Agents update rolls out. Without the gate, everything still works and replies arrive whole instead of streaming.

## Configuration

The npm scripts read every setting from `.env` (via `--env-file-if-exists`):

| Variable | Required | What it does |
|---|---|---|
| `ANTHROPIC_API_KEY` | no | API key from [platform.claude.com](https://platform.claude.com/). Skip it after `ant auth login`: the SDK discovers CLI credentials |
| `CLAUDE_AGENT_ID` | yes | The analyst agent, printed by `npm run setup` |
| `CLAUDE_ENVIRONMENT_ID` | yes | The agent's sandbox environment, printed by `npm run setup` |
| `PORT` | no | Where the server listens (default `3000`). The chat UI is served from the same port |
| `HOST` | no | Bind address (default `127.0.0.1`). Set `0.0.0.0` only after replacing the demo `getUser` |
| `QUICKSTART_MODEL` | no | Overrides the agent's model at provisioning time |

| Command | What it does |
|---|---|
| `npm run setup` | One-time provisioning: creates the agent and its environment, prints their IDs |
| `npm run update-agent` | Pushes an edited `setup/agent-config.ts` onto the existing agent as a new version |
| `npm run dev` | Runs the server, restarting on change. Edits to `web/` apply on browser reload |
| `npm start` | Runs the server once, no watcher |

The agent's entire identity (name, model, and system prompt) lives in `setup/agent-config.ts`. After editing it, run `npm run update-agent`: re-running `npm run setup` would create a duplicate agent.

## Deployment

Two things gate every deployment:

- The demo `getUser` in `src/bot.ts` trusts every caller, which is why the default bind is loopback. Replace it with your real session lookup before setting `HOST`. See "getUser is the security boundary" in `skill.md`.
- A research turn holds the `/api/chat` response open for minutes. The server never reaps it, but a reverse proxy in front will at its own idle default (often 60 seconds). Raise that timeout.

Three shapes fit this server:

| Target | Fit |
|---|---|
| VM or container | `npm start` with `HOST=0.0.0.0`. One long-lived process, streams held as long as a turn needs |
| Cloudflare Workers, Vercel, Netlify | The `/api` routes are fetch-native [Hono](https://hono.dev/) handlers and drop into those adapters. Serve the page as a prebuilt static asset, and move turns into a queue: request-duration caps don't fit responses held open for minutes |
| Multiple instances | Swap `createMemoryState()` for `createRedisState()` in `src/bot.ts`, and sticky-route each conversation to one instance |

## Files

| | |
|---|---|
| `setup/agent-config.ts` | Model + system prompt: the agent's entire behavior |
| `setup/create-agent.ts` | One-time provisioning: the analyst agent and its environment |
| `src/main.ts` | The server (Hono on Node): the chat page, `/api/chat`, `/api/sessions`, `/api/history`, `/api/activity` |
| `src/bot.ts` | Chat SDK instance, web adapter, `getUser` (the auth boundary), message handler |
| `src/managed-agents.ts` | The bridge: the turn loop, token previews, the session ownership check |
| `src/sessions.ts` | The sidebar's data source: list, create, and replay sessions |
| `src/card.tsx` | The "brief ready" JSX card and its web fallback |
| `src/activity.ts` | In-process fan-out of turn activity to live subscribers |
| `web/` | The chat page: React + `useChat`, the sidebar, the activity feed, bundled by esbuild |
| `skill.md` | Setup walkthrough, gotchas, debugging |

## Versions

- Node 22.9 or later. No build step: `tsx` runs the TypeScript, and `src/main.ts` bundles the page with esbuild on request.
- `chat`, `@chat-adapter/web`, and `@chat-adapter/state-memory` are pinned to `4.30.0`. The Chat SDK releases in lockstep and moves fast.
- `@anthropic-ai/sdk` 0.109.0 or later: the first release with `event_deltas` and the `accumulateManagedAgentsEvent` helper.
