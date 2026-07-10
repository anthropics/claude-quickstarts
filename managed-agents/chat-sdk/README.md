# Chat SDK × Claude Managed Agents

A devtools VC research analyst in a browser chat window. Vercel's [Chat SDK](https://chat-sdk.dev/) handles the chat surface, and one persistent [Managed Agent](https://platform.claude.com/docs/en/managed-agents/overview) session per conversation does the research, streaming its reply token by token while a live feed shows the tool calls it is making. The sidebar lists your past conversations, and every one of them is just a Managed Agents session: the server keeps no state at all.

```
sidebar ──▶ GET/POST /api/sessions ─────▶ /v1/sessions (list, create)
        ──▶ GET /api/history ───────────▶ /v1/sessions/{id}/events (replay)

browser (useChat) ──▶ POST /api/chat ──▶ onDirectMessage
                                              │ conversation ID
                                              │ = session ID          ┌───────────────────┐
   held HTTP response ◀── thread.post() ◀─────┴──▶ session ──────────▶│ VC analyst (opus) │
   (the reply types itself out,               │                       │ web search, fetch │
    then the "brief ready" card)              │                       └───────────────────┘
   /api/activity (SSE) ◀── TurnHooks.activity ┘    event_start / event_delta,
   (web_search: ..., thinking)                     agent.message, tool_use
```

The only credential is Anthropic auth. The Chat SDK's [web adapter](https://chat-sdk.dev/adapters/official/web) speaks the AI SDK message stream protocol straight to the browser, so there is no Meta or Slack app to register, no webhook to verify, and no tunnel: `bun run dev` and open `localhost:3000`.

## Why this pairing

A chat bot has two hard halves and they're entirely different problems. The Chat SDK owns the messaging surface: the `useChat` stream protocol, markdown rendering, thread identity, and one `onDirectMessage` handler that also fires for Slack, Teams, Discord, and WhatsApp. Managed Agents owns the agent: the tool loop, the sandbox, web search, and the conversation itself. The bridge between them (`src/managed-agents.ts` plus `src/bot.ts`) is a few hundred lines.

The pairing works because each side is stateful exactly where the other is weak. The web surface is stateless: the browser holds the transcript and resends it on every request, and there is no platform history API behind it. A Managed Agents session holds the whole conversation server-side. This demo pushes that to its logical end: **the `useChat` conversation ID is the session ID**, so there is no mapping table, no database, and no transcript store anywhere in the app. Compaction and prompt caching happen inside the session, and follow-ups land in context because the analyst remembers what it already researched.

The shapes match, too. Research turns run for minutes, which fights every request/response pattern but fits this adapter natively: it holds one response stream open per turn and pumps each `thread.post()` onto it. The agent's "on it" acknowledgment renders in seconds, the activity feed shows the searches while you wait, and the brief streams in minutes later on the same response.

One bonus: the Chat SDK normalizes Slack, Teams, Discord, Telegram, and WhatsApp behind the same thread API, so the bridge in `src/managed-agents.ts` ships to those channels by swapping the adapter. One line in the handler moves with it: webhook surfaces have to ack in seconds and post replies through the platform API later, so `src/bot.ts` goes back to fire-and-forget there instead of awaiting the turn (see `skill.md`, "Two held streams"). The web adapter is the zero-credential way to build and demo the agent first.

## Sessions are the state

Most chat apps grow a conversations table on day two. This one asks the Managed Agents API instead:

- **The sidebar** is `GET /api/sessions` → `client.beta.sessions.list({ agent_id })`. Sessions belonging to this agent, newest first, archived ones excluded by the API itself.
- **New chat** is `POST /api/sessions` → `sessions.create()`. The returned session ID becomes the `useChat` conversation ID; the first message you send retitles the session (`sessions.update`), so the sidebar and the Anthropic Console both show what the chat is about.
- **Opening an old chat** is `GET /api/history` → `sessions.events.list()`. The transcript is rebuilt from the session's own event log: `user.message` and `agent.message` events become bubbles, and even the "brief ready" card is re-derived from the `agent.tool_use` events and timestamps of each turn. Nothing was stored, so nothing can be stale.

Kill the server, restart it, reload the page: every conversation and every transcript comes back, because none of it ever lived in the server. The one Chat SDK state adapter in `src/bot.ts` (`createMemoryState()`) holds only SDK internals like message dedup, which is why losing it on restart costs nothing.

Because conversation IDs arrive from the browser and become API path parameters, every route that touches a session first passes it through `ownedSession()` (`src/managed-agents.ts`): the ID must parse, resolve, belong to this quickstart's agent, and not be archived. Without that check, `/api/history` would happily replay any session the server's API key can see.

## Token streaming, end to end

Managed Agents sessions can interleave **previews** into the event stream: open it with `event_deltas: ["agent.message"]` and the server sends `event_start` when the model begins a message, then `event_delta` text fragments as it writes, then the buffered `agent.message` that was always there. The bridge turns each preview into a streamed `thread.post(asyncIterable)`, the web adapter turns each fragment into an SSE `text-delta`, and `useChat` renders them, so Managed Agents tokens reach the page with nothing in between buffering a full message.

Previews are best-effort and never persisted; the buffered event is authoritative. Because a preview is always a verbatim prefix of its buffered event, the bridge finishes a streamed reply by posting `final.slice(alreadySent.length)` and closing. In an org without the streaming gate the same loop degrades to one post per buffered message: the pre-streaming behavior, same code path.

The reply is assembled with the SDK's own reducer, `accumulateManagedAgentsEvent` from `@anthropic-ai/sdk/lib/sessions/accumulate`: each `event_start`/`event_delta`/`agent.message` folds into one snapshot per message ID, and the bridge streams out whatever suffix each fold added.

## The "brief ready" card

When a research turn finishes, the bridge closes it with a Chat SDK **JSX card** (`src/card.tsx`): a title, the turn's stats (web searches, wall-clock time), and a link button to the session's live trace in the Anthropic Console.

```tsx
<Card title="Brief ready" subtitle={`${searches} web searches · ${duration}`}>
  <Actions>
    <LinkButton url={consoleTraceUrl(sessionId)} label="Open session trace" />
  </Actions>
</Card>
```

Cards are the Chat SDK's portable rich-UI primitive: the same element renders as Slack Block Kit or Teams Adaptive Cards if you swap the adapter. The web adapter has no card renderer in v1 and sends the card's `fallbackText` instead, so the fallback is a fenced ` ```card ` block of JSON that `web/app.tsx` parses (strictly — the session ID is validated before it becomes a link) and renders as a styled card. One post, both surfaces.

## What the activity feed shows

The web adapter carries message text only, but the session event stream the bridge is already reading carries everything else: `agent.tool_use` (with its input), `agent.tool_result`, `agent.thinking`, `span.model_request_start`, `session.error`. The bridge reports those through a `TurnHooks.activity` callback, `src/main.ts` fans them out on `GET /api/activity?conversation=...` (a second, message-free SSE route), and the page renders the last few while the turn runs:

```
model request
thinking
web_search: Zed editor funding round Series investors
web_fetch: https://zed.dev/pricing
writing the reply
```

then collapses them to "12 tool calls · 5 model requests" once the reply lands. Nothing is stored or replayed; the transcript is the record, this is the progress lane.

## Quickstart

```bash
cd managed-agents/chat-sdk
bun install
claude
```

Then ask: **"walk me through setting this up."** Claude reads [`skill.md`](./skill.md) and drives the whole thing. Or by hand:

```bash
cp .env.example .env      # add ANTHROPIC_API_KEY, or `ant auth login` once and leave it out
bun run setup             # one-time: one agent + one environment; paste the printed IDs into .env
bun run dev               # then open http://localhost:3000 and ask "look at Biome"
```

Token previews (`event_deltas`) are part of the 2026-07-01 Managed Agents update and are gated per organization. Without the streaming gate everything still works and replies arrive whole instead of streaming.

## Files

| | |
|---|---|
| `setup/agent-config.ts` | Model + system prompt: the agent's entire behavior |
| `setup/create-agent.ts` | One-time provisioning: the analyst agent and its environment |
| `src/main.ts` | Bun server: the chat page, `/api/chat`, `/api/sessions`, `/api/history`, `/api/activity` |
| `src/bot.ts` | Chat SDK instance, web adapter, `getUser` (the auth boundary), message handler |
| `src/managed-agents.ts` | The bridge: the turn loop, token previews, the session ownership check |
| `src/sessions.ts` | The sidebar's data source: list, create, and replay sessions |
| `src/card.tsx` | The "brief ready" JSX card and its web fallback |
| `src/activity.ts` | In-process fan-out of turn activity to live subscribers |
| `web/` | The chat page: React + `useChat`, the sidebar, the activity feed, bundled by Bun |
| `skill.md` | Setup walkthrough, gotchas, debugging |

Runtime is Bun (1.2.3 or later: `src/main.ts` serves `web/index.html` through an HTML import). `chat`, `@chat-adapter/web`, and `@chat-adapter/state-memory` are pinned to 4.30.0 (the Chat SDK releases in lockstep and moves fast). `@anthropic-ai/sdk` needs 0.109.0 or later: that release (2026-06-30) is the first with `event_deltas` and the `accumulateManagedAgentsEvent` helper.
