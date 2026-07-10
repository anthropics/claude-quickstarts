# Chat SDK × Claude Managed Agents

A devtools VC research analyst in a browser chat window. Vercel's [Chat SDK](https://chat-sdk.dev/) handles the chat surface, and one persistent [Managed Agent](https://platform.claude.com/docs/en/managed-agents/overview) session per conversation does the research, streaming its reply token by token while a live feed shows the tool calls it is making. The sidebar lists your past conversations, and every one of them is just a Managed Agents session: the server keeps no state at all.

The pairing works because each side is stateful exactly where the other is weak. The Chat SDK owns the messaging surface: the `useChat` stream protocol, markdown rendering, thread identity, and one `onDirectMessage` handler that also fires for Slack, Teams, Discord, and WhatsApp. Managed Agents owns the agent: the tool loop, the sandbox, web search, and the conversation itself. **The `useChat` conversation ID is the session ID**, so there is no mapping table, no database, and no transcript store anywhere in the app; compaction and prompt caching happen inside the session, follow-ups land in context because the analyst remembers what it already researched, and the bridge between them is a few hundred lines. Architecture and design notes live in [`CLAUDE.md`](./CLAUDE.md) and [`skill.md`](./skill.md).

The only credential is Anthropic auth. The Chat SDK's [web adapter](https://chat-sdk.dev/adapters/official/web) speaks the AI SDK message stream protocol straight to the browser, so there is no Meta or Slack app to register, no webhook to verify, and no tunnel.

## Quickstart

Needs Node 22.9 or later.

```bash
cd managed-agents/chat-sdk
npm install
claude
```

Then ask: **"walk me through setting this up."** Claude reads [`skill.md`](./skill.md) and drives the whole thing. Or by hand:

```bash
cp .env.example .env      # add ANTHROPIC_API_KEY, or `ant auth login` once and leave it out
npm run setup             # one-time: one agent + one environment; paste the printed IDs into .env
npm run dev               # then open http://localhost:3000 and ask "look at Biome"
```

Token previews (`event_deltas`) are part of the 2026-07-01 Managed Agents update and are gated per organization. Without the streaming gate everything still works and replies arrive whole instead of streaming.

## Configuration

Everything is environment variables, read from `.env` by the npm scripts (`--env-file-if-exists`):

| Variable | Required | What it does |
|---|---|---|
| `ANTHROPIC_API_KEY` | no | An API key from [platform.claude.com](https://platform.claude.com/). Leave it unset after `ant auth login` once; the SDK discovers CLI credentials |
| `CLAUDE_AGENT_ID` | yes | The analyst agent, printed by `npm run setup` |
| `CLAUDE_ENVIRONMENT_ID` | yes | The agent's sandbox environment, printed by `npm run setup` |
| `PORT` | no | Where the server listens (default 3000). The chat UI is served from the same port |
| `HOST` | no | Bind address (default `127.0.0.1`). Loopback-only on purpose: the demo has no real auth. Set to `0.0.0.0` only after replacing `getUser` |
| `QUICKSTART_MODEL` | no | Override the agent's model, read by `setup/agent-config.ts` at provisioning time |

| Command | What it does |
|---|---|
| `npm run setup` | One-time provisioning: creates the agent and its environment, prints their IDs |
| `npm run dev` | Runs the server, restarting on change (`tsx watch`); web/ edits apply on browser reload |
| `npm start` | Runs the server once, no watcher |

The agent's entire behavior -- model and system prompt -- lives in `setup/agent-config.ts`. Editing it and re-running `npm run setup` would create a duplicate agent; update the existing one instead (see `skill.md`, Production notes).

## Deployment

Two things gate every deployment, wherever it lands:

- **Auth first.** The demo `getUser` in `src/bot.ts` trusts every caller, which is why the server binds to the loopback interface by default. Before exposing it, replace `getUser` with your real session lookup, then set `HOST` to your bind address -- see "getUser is the security boundary" in `skill.md`.
- **Long-held responses.** A research turn holds the `/api/chat` response open for minutes. The server never reaps it, but any reverse proxy or load balancer in front will at its own idle default (often 60 seconds); raise that timeout for this route.

Options, in order of fit:

- **A VM or container** running `npm start` with `HOST=0.0.0.0` is the natural shape: one long-lived process, streams held as long as the turn needs.
- **Cloudflare Workers, Vercel, Netlify:** the four `/api` routes are fetch-native [Hono](https://hono.dev/) handlers, so they drop into those adapters; the page routes read files and run esbuild at runtime, so serve the page as a prebuilt static asset there. The bigger catch is request-duration caps (most serverless platforms have them, free tiers aggressively): they don't fit a response that stays open for minutes, so on those hosts move the turn into a queue and notify the browser another way.
- **Multiple instances** need two changes: swap `createMemoryState()` for `createRedisState()` in `src/bot.ts` so message dedup holds across instances, and sticky-route each conversation to one instance (the turn serialization is process-local).

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

Runtime is Node 22.9 or later (`--env-file-if-exists` in the npm scripts loads `.env`); `tsx` runs the TypeScript directly and `src/main.ts` bundles the page with esbuild on request, so there is no build step. `chat`, `@chat-adapter/web`, and `@chat-adapter/state-memory` are pinned to 4.30.0 (the Chat SDK releases in lockstep and moves fast). `@anthropic-ai/sdk` needs 0.109.0 or later: that release (2026-06-30) is the first with `event_deltas` and the `accumulateManagedAgentsEvent` helper.
