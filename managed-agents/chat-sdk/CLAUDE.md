# Chat SDK × Claude Managed Agents analyst

Long-running Node server (Hono): browser chat with a sessions sidebar (`useChat` → `/api/chat`) → Chat SDK web adapter `onDirectMessage` → one Managed Agents session per conversation, where **the conversation ID is the session ID** (no mapping, no database; the sidebar is `sessions.list`, transcript replay is `sessions.events.list`) → a held session event stream (opened with `event_deltas` token previews, always on) feeds each fragment back onto the same HTTP response while `/api/activity` streams the tool calls and thinking the page shows as a live feed. Each research turn closes with a Chat SDK JSX card ("Brief ready", `src/card.tsx`) whose web fallback the page renders as a styled card.

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

Needs `@anthropic-ai/sdk` ≥ 0.109.0 (the first release with `event_deltas` and `accumulateManagedAgentsEvent`); streaming is gated per org while the 2026-07-01 update rolls out (`skill.md`, "Token previews are gated per org").

## When the user asks to set this up, get it working, or debug it

1. **Invoke `/claude-api` first.** That skill loads the full Managed Agents API reference (agents, sessions, environments, events, webhooks, outcomes, multiagent, vaults, memory stores). Use it as the source of truth for any SDK call you write or edit. Don't guess field names.
2. **Read `./skill.md`** and walk the user through it step by step. It has the ordered checklist, every gotcha (the awaited handler and why fire-and-forget breaks here, preview reconciliation, sessions-as-state and the `ownedSession` check on browser-supplied conversation IDs, `getUser` as the single auth boundary for all four API routes, the never-stored card and its strict client-side validation, the streaming org gate, proxies reaping the held response), and the debugging table.
3. **After the base bot works, offer extensions.** Ask the user which (if any) they want, then edit `setup/agent-config.ts`, `setup/create-agent.ts`, and/or `src/managed-agents.ts` accordingly:
   - **Multiagent red-team pass**: a second toolless reviewer agent on the analyst's roster (`multiagent: {type: "coordinator", agents: [...]}`) that critiques every draft brief in a session thread; the handoff events (`session.thread_created`, `agent.thread_message_sent/received`) arrive on the same stream the bridge already reads, so they can feed the activity feed
   - **Memory store**: the analyst remembers the partner's thesis and portfolio across sessions (`resources: [{type: "memory_store", ...}]` on `sessions.create`)
   - **Outcomes**: rubric-grade each brief before it sends (`user.define_outcome` event instead of `user.message`)
   - **GitHub repo mount**: diligence an open-source repo from the inside (`resources: [{type: "github_repository", ...}]`)
   - **MCP tools**: wire a market-data MCP server (`mcp_servers` + `mcp_toolset` on the agent, credentials via a vault, `vault_ids` on the session)
   - **Another surface**: add the Slack, Teams, Discord, or WhatsApp adapter next to the web one in `src/bot.ts`. The bridge doesn't change (and the JSX card starts rendering natively), but those are webhook surfaces: the handler must ack in seconds and post later, so dispatch their turns fire-and-forget instead of awaiting (see `skill.md`, "Two held streams")
   - **Re-enable bash**: only with an approval surface. It's disabled because the agent reads untrusted web pages (see `skill.md`, "Why bash is off")

   Pull exact shapes from the `/claude-api` skill's `shared/managed-agents-*.md` docs.

Run the server with `npm run dev` and open `http://localhost:3000`. One-time agent provisioning is `npm run setup`.
