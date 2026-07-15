# Setup tips & tricks: Chat SDK web adapter × Claude Managed Agents

Things that aren't obvious from the docs and tend to cost debugging time.

---

## Mental model

### The conversation ID is the session ID

Every browser conversation is a DM on a durable thread (`web:{userId}:{conversationId}`), and in this quickstart the `conversationId` half is a Managed Agents session ID, verbatim. The page creates the session first (`POST /api/sessions` → `sessions.create()`), hands the returned ID to `useChat` as its `threadId`, and every message in that conversation lands in that session. There is no mapping table: the bridge decodes the session ID back out of the thread ID (`adapters.web.decodeThreadId`) and uses it directly.

That makes the Managed Agents API the entire conversation store:

- The sidebar is `sessions.list({ agent_id })` -- server-side filter, archived sessions excluded by default.
- Opening an old chat is `sessions.events.list()`: `user.message` and `agent.message` events become bubbles again (`src/sessions.ts`). The session also holds all research context server-side, so follow-ups into a replayed chat work -- the analyst remembers what it already researched.
- The first message of a fresh conversation doubles as its title: it travels as `useChat` message metadata and the bridge writes it with `sessions.update()`, so the sidebar and the Console agree on what the chat is about.

The server keeps nothing. `createMemoryState()` in `src/bot.ts` holds only Chat SDK internals (message dedup, locks), and `persistMessageHistory: false` keeps the adapter from caching message bodies there too -- the browser holds the live transcript, the session holds the durable one.

### Never trust a conversation ID

The flip side of "the browser sends a session ID" is that the browser sends a session ID. It becomes an API path parameter, and the server's Anthropic credentials can see every session in the workspace -- including other agents' sessions. `ownedSession()` in `src/managed-agents.ts` is the gate every session-touching route goes through: the ID must look like an ID, resolve, belong to this quickstart's agent, and not be archived. `/api/history` 404s without it; `runTurn` refuses the turn. If you fork this, keep that function in the path of anything that takes a conversation ID from a client.

### Two held streams, no webhooks

`useChat` POSTs to `/api/chat` and the web adapter answers with a response stream it keeps open until the handler returns. Inside the handler, the bridge holds an Anthropic SSE stream open for the same turn and forwards each `agent.message` with `thread.post()`, which the adapter writes onto the response as its own text part. So the acknowledgment renders in the browser within seconds and the brief lands on the same response minutes later. There is no Anthropic webhook, no platform webhook, and no `ANTHROPIC_WEBHOOK_SIGNING_KEY` in this quickstart.

This is why `src/bot.ts` awaits the turn instead of firing and forgetting. The Slack and WhatsApp adapters need the opposite (ack the platform webhook in seconds, post through their API later); on web, returning early closes the only channel the reply can travel on.

Porting to a webhook surface also changes where sessions come from. There is no browser to create one, so the handler creates a session for each new platform thread and keeps the mapping (thread metadata, or a small table) -- the web shortcut of using the session ID as the conversation ID doesn't travel.

### Previews stream the message being written

The bridge opens the event stream with `event_deltas: ["agent.message"]` (`src/managed-agents.ts`). That one query param is the whole token-streaming feature, and it is always on here. With it, three things arrive for every agent message instead of one: `event_start` (the id a buffered `agent.message` will carry), a run of `event_delta` text fragments while the model writes, then the buffered `agent.message` itself. On `event_start` the bridge opens a streamed `thread.post(asyncIterable)` so the bubble appears immediately; each fragment is pushed straight through; the buffered event closes it.

Two rules make this safe to copy:

- **The buffered event is the truth.** Previews are best-effort, never persisted, and always a verbatim prefix of the final text, so reconciliation is `final.slice(sent.length)` then end. A preview whose buffered event never comes (its model request errored) is closed by `span.model_request_end`.
- **No previews must mean no change.** In an org without session streaming, or on an `@anthropic-ai/sdk` without `event_deltas`, the same loop sees only buffered events and posts each one whole. That is the entire pre-streaming behavior, preserved as the degraded path rather than as a second code path.

### The activity feed is a second lane

The web adapter v1 carries message text only (no tool or data parts), so progress does not travel through `thread.post`. Instead the bridge reports every interesting event -- `agent.tool_use` with a short input hint, `agent.tool_result`, `agent.thinking` (start-only: Managed Agents says that the model is reasoning, not what), `span.model_request_start`, retries -- through the `TurnHooks.activity` callback, and `src/app.ts` fans those out per thread on `GET /api/activity?conversation=...`. The page tails it with an `EventSource` while a turn runs and collapses it to a count afterward. Nothing is stored: a tab that attaches mid-turn sees the rest of the turn, a reload sees nothing, and the chat lane stays pure Chat SDK.

### The card is one post, two renderings

`runTurn` closes every research turn (any turn that called `web_search`) with a Chat SDK **card** built in `src/card.tsx`: JSX (`@jsxImportSource chat`) with a `LinkButton` to the session's Console trace, plus a `fallbackText`. On Slack or Teams the JSX renders natively (Block Kit / Adaptive Cards). The web adapter has no card renderer in v1 and sends `fallbackText` instead, so the fallback is a fenced ` ```card ` block of JSON and `web/app.tsx` renders that fence as a styled card.

Two details worth keeping if you copy the pattern:

- **The page validates the fence strictly** (numeric stats, session ID shape) before the JSON becomes a link, because agent-authored text flows through the same renderer and a prompt-injected page could imitate the fence. Worst case after validation is a cosmetic box linking to the Anthropic Console.
- **The card is never stored.** It isn't an `agent.message`, so it doesn't exist in the session's event log. `/api/history` re-derives it from the log instead -- `agent.tool_use` events and `processed_at` timestamps per turn -- which is a nice proof that the event log really is the single source of truth.

### Stream first, then send

`src/managed-agents.ts` opens `events.stream()` before `events.send()`. The stream only delivers events emitted after it opens, so the reverse order can miss the start of the turn.

### The response is the progress UI

There is no typing indicator on web (`startTyping` is a no-op in the web adapter). `useChat` derives `status` from the response itself: it sits at `"streaming"` from the moment the adapter opens the stream until the turn ends, so the page shows a working indicator for the whole research run with no extra plumbing. The agent's "on it" acknowledgment (a real `agent.message`, prompted in `setup/agent-config.ts`) is the durable progress signal.

### getUser is the security boundary

Slack and WhatsApp sign every webhook; a browser request proves nothing. The `getUser` function in `src/bot.ts` is where identity comes from, for every route that exposes a conversation: the web adapter calls it on each `/api/chat` POST, and `src/app.ts` runs the same check (via `authenticate`) before `/api/activity`, `/api/sessions`, and `/api/history`. Returning `null` produces a 401 everywhere. The demo's `getUser` accepts everyone as the same `local` user, which is exactly right on `localhost` and exactly wrong anywhere else: anyone who can reach the port can run research turns on your bill, list your sessions, and replay their transcripts. `src/main.ts` binds to loopback (`127.0.0.1`) by default for that reason. Before exposing it, replace `getUser` with your real session lookup (NextAuth, Clerk, a session cookie) -- and scope the session routes to the resolved user, e.g. by writing the user ID into session `metadata` at create time and filtering on it in `listSessions` and `ownedSession`.

### Why bash is off

The agent reads arbitrary, untrusted web pages. A prompt-injected page plus an auto-approved shell plus open egress is an exfiltration path, and this chat UI offers no approval surface to gate it. So `setup/create-agent.ts` disables bash (`configs: [{ name: "bash", enabled: false }]`) and the brief runs on web search, web fetch, and the file tools. Re-enable bash only where a human can approve tool calls (`permission_policy: { type: "always_ask" }` plus a client that answers `user.tool_confirmation`).

One tool you'll see in the logs that you didn't enable: `repl`. It's the toolset's built-in programmatic tool calling. The agent writes short scripts that compose the tools you did enable (`await web_search(...)` in a loop, for example), and the scripts run inside the same session sandbox. It isn't individually configurable: the per-tool `configs` names are `bash, edit, glob, grep, read, web_fetch, web_search, write`.

The environment uses unrestricted egress because networking posture follows what's in the sandbox. Here the sandbox holds no secrets and no shell, so there is nothing for a hostile page to steal or run. The residual risk (a fetched URL encoding chat content) is real for any web-researching agent. If your fork handles sensitive conversations, switch to `limited` networking with an allowlist.

---

## Gotchas

### Token previews are gated per org

`@anthropic-ai/sdk` 0.109.0 (2026-06-30) is the first published release with `event_deltas` and the `accumulateManagedAgentsEvent` helper, both under the standard `managed-agents-2026-04-01` beta header the SDK sends for you. The streaming feature itself is still enabled per organization while the 2026-07-01 update rolls out. Without the gate everything works and nothing streams: the `event_deltas` query param is silently ignored, no `event_start` ever arrives, and every reply posts whole. That is the org, not your code.

### Stop abandons the response, not the research

The Stop button (it replaces Send while a turn runs) aborts the browser's request. The bridge does not watch that signal: the Managed Agents turn keeps running server-side, its replies go nowhere, and a message you send right afterwards queues behind it server-side; the bridge discards the abandoned turn's replies rather than posting them into your new request (the event log keeps them -- reopen the chat to see them). Don't read "I pressed stop and the next answer took ages" as a hang. Picking the chat again from the sidebar after the turn finishes replays everything, including the replies that went nowhere -- the event log kept them.

### Restarts are free, but live turns aren't

Because the state is the sessions API, restarting `npm run dev` costs nothing: the sidebar and every transcript come back. The exception is a turn in flight at restart -- its held response dies with the process, and the browser shows a network error. The session finishes the turn server-side anyway; reopen the chat from the sidebar and the replies are there.

### Markdown renders for real now

`thread.post()` takes standard markdown. On Slack or WhatsApp the Chat SDK converts it to the platform's markup; on web it passes through and `web/app.tsx` renders it with `react-markdown`. The system prompt still bans headings, tables, and code fences, not because they'd break, but because the output is a chat bubble and the analyst should read like a colleague texting, not a report generator.

### Don't put a default proxy in front of it

The `/api/chat` response stays open for the whole research turn, minutes at a time. `src/main.ts` disables Node's own request timeout (`requestTimeout: 0`; the socket inactivity timeout is already off by default), but a reverse proxy or load balancer in front will reap a quiet response at its own default (often 60 seconds) and the browser sees a network error right when the brief was due. Locally there is nothing in between; when you deploy, raise the proxy's idle/read timeout for this route.

---

## Setup checklist

1. `cp .env.example .env`, then add Anthropic auth: uncomment and fill in `ANTHROPIC_API_KEY`, or run `ant auth login` once and leave it out (the SDK discovers CLI credentials). Token previews are part of the 2026-07-01 Managed Agents update; use an org that has it.
2. `npm install` (needs Node ≥ 22.9 and `@anthropic-ai/sdk` ≥ 0.109.0; `package.json` already says so).
3. `npm run setup` → copy the printed `CLAUDE_AGENT_ID` and `CLAUDE_ENVIRONMENT_ID` into `.env`.
4. `npm run dev` → open `http://localhost:3000` → **New chat** → ask for a brief on any topic. Expect the acknowledgment within seconds, the activity feed filling with searches for a minute or three, the brief typing itself out, then the **Brief ready** card with the turn's stats and a link to the session trace. Restart the server and reload to see the sidebar and transcript come back from the sessions API.

---

## Deploying off the Node server

The four `/api` routes are one platform-neutral Hono app (`src/app.ts`) whose every import is Web-standard. `src/main.ts` is the shipped host (the local Node server, which also builds the page on request); any host that can run a fetch handler can mount the same app: use `deployedApi()` instead of `api`, and serve the page statically (lift the esbuild recipe from `bundleApp` in `src/main.ts` -- the `process.env.NODE_ENV` define is load-bearing for React).

What changes when you leave the Node server:

- **Credentials travel as platform config.** Set `ANTHROPIC_API_KEY`, `CLAUDE_AGENT_ID`, and `CLAUDE_ENVIRONMENT_ID` as env vars or secrets on the platform. CLI credentials (`ant auth login`) only exist on your machine, which is why a deployed host mounts `deployedApi()`: it 500s with a named variable when config is missing, instead of failing deep inside the SDK on the first call. One requirement on the host: the Anthropic client reads `process.env` at module scope (`src/managed-agents.ts`), so secrets must be in `process.env` before imports run -- on non-Node runtimes, enable the platform's Node-compat env shim.
- **Mind the duration cap.** `/api/chat` holds its response open for the whole research turn, minutes at a time. Serverless synchronous function limits are often seconds; verify the platform allows long streaming responses before relying on it, or move the turn into a queue.
- **Gate the deploy before it exists.** The demo `getUser` trusts every caller, so an unprotected URL lets anyone research on your bill and read every transcript. Turn on the platform's access protection first, and treat it as a stopgap until `getUser` is real.
- The activity feed's fan-out is in-process (`src/activity.ts`). A host that routes `/api/activity` to a different instance than the turn's `/api/chat` shows an empty feed for that turn. Cosmetic: the chat lane is unaffected.
- The Chat SDK's message dedup lives in `createMemoryState()`, also per-instance. Duplicate deliveries of the same message ID could each start a turn. `useChat` sends each message once, so this matters when you add retries or a second surface; `createRedisState()` is the fix (see the multi-instance note below).

---

## Debugging a failed run

| Symptom | Likely cause |
|---|---|
| Every request fails with a generic `404 not found`, starting with the first one | The org has no Managed Agents access at all (the SDK sends the `managed-agents-2026-04-01` beta header on every call). Use an org that does; it's not your code |
| Replies arrive but never stream | The org doesn't have session streaming enabled (no `event_start` ever arrives), or the SDK in `node_modules` is older than 0.109.0 and doesn't know `event_deltas`. Everything else still works |
| Page loads but Send does nothing, `/api/chat` red in the network tab | The server isn't running, or the tab is pointed at a stale port. `npm run dev` and reload |
| `EADDRINUSE` on startup | A forgotten server still holds the port. `lsof -ti:3000 -sTCP:LISTEN \| xargs kill`, then start exactly one |
| `/api/chat` returns 401 | `getUser` returned `null` or threw. The shipped demo never 401s; this appears once you wire in real auth |
| `/api/history` returns 404 for a session you can see in the Console | `ownedSession` rejected it: the session belongs to a different agent than `CLAUDE_AGENT_ID`, or it's archived. The sidebar only lists this agent's sessions for the same reason |
| "This session has ended on the server" | The session behind the conversation was archived, deleted, or terminated (or `.env` now points at a different agent). Start a new chat; the old transcript is still in the Console |
| `400 Invalid agent ID` | `.env` still has the `agent_...` placeholder. Re-paste from `npm run setup` |
| Acknowledgment arrives, then a network error instead of the brief | Something between the browser and the server reaped the long-lived response. Hit the server directly, or raise the proxy's idle timeout. The turn finished server-side: reopen the chat from the sidebar to see it |
| "I lost my connection mid-research, but the work continues on the server" | The Anthropic event stream dropped mid-turn. Don't resend (that would queue a duplicate research run); reopen the chat from the sidebar once the turn finishes |
| Replaying the same request with `curl` returns an empty assistant turn | The Chat SDK dedupes processed message IDs through the state adapter. Mint a new message `id` per request; `useChat` always does |
| `Research run stopped early (retries_exhausted)` | The model or sandbox hit repeated errors (`session.error` lines in the server log say which, commonly model overload). Transient: send the message again |
| "The agent asked for an approval this bridge doesn't handle" | The agent config was edited to include an `always_ask` tool or a custom tool. This bridge has no approval surface, and the session stays parked waiting for the confirmation -- fix the config (`always_allow`, or build the `user.tool_confirmation` round-trip) and start a new chat; the stuck conversation stays stuck |

---

## Production notes

- Changed `setup/agent-config.ts`? Run `npm run update-agent`. It pushes the new name, model, and system prompt onto the existing agent as a new version (`agents.update`): running sessions keep their pinned version, new chats use the latest. Never re-run `npm run setup` for this -- it would create a duplicate agent.
- Replace the demo `getUser` with your real session lookup and return `null` for anonymous requests. This is the only thing between the public internet and your API budget. Then scope sessions per user: write the resolved user ID into session `metadata` on create and filter on it in `listSessions`/`ownedSession`, so one user cannot list or replay another's conversations.
- Deploy anywhere that lets a response stream stay open for minutes: a VM or container running `npm start` works once you set `HOST` to your bind address (the default `127.0.0.1` is loopback-only on purpose). For serverless hosts, see "Deploying off the Node server" above.
- Multiple server instances need two things: swap `createMemoryState()` for `createRedisState()` (set `REDIS_URL`) so the Chat SDK's message dedup holds across instances, and route each conversation to one instance (sticky sessions on the conversation ID) -- the turn serialization in `src/managed-agents.ts` is process-local, and two instances streaming the same session would each post every reply.
- Gate spend even behind auth: check the resolved user ID against an allowlist in `getUser`, or rate-limit per thread in the message handler.
- Proactive sends (scheduled briefs) have no path on web v1: the adapter can only write during a request it is answering. Use one of the push-capable adapters (Slack, Telegram, WhatsApp) for anything the bot initiates.
- The server log carries event types, tool names, and session IDs, never message content. Keep it that way if you add logging, and give the sink a retention policy.
- Cleanup when you're done with the demo (archive is permanent; archiving the agent also hides its sessions from the sidebar):

```bash
node --env-file-if-exists=.env --input-type=module -e 'const client = new (await import("@anthropic-ai/sdk")).default();
await client.beta.agents.archive(process.env.CLAUDE_AGENT_ID);
await client.beta.environments.archive(process.env.CLAUDE_ENVIRONMENT_ID);'
```
