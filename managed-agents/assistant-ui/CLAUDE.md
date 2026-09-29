# assistant-ui × Claude Managed Agents

A Next.js chat app. assistant-ui renders everything; one Managed Agents session per conversation runs the analyst, and `lib/managed-agents/reducer.ts` folds each session's event log into the messages assistant-ui renders. The sidebar is the session list. There is no database. Needs Node 22+, `@anthropic-ai/sdk` 0.109.0 or later (`event_deltas` + session event helpers), and `@assistant-ui/react` 0.14.27 or later (the `defineToolkit`/`Tools` API and approvals on `useExternalStoreRuntime`).

## When the user asks to set this up, get it working, or debug it

1. **Invoke `/claude-api` first.** It is the source of truth for every SDK call in `app/api/` and every field in `agents/` and `environments/` (agents, environments, sessions, events, files, resources). Don't guess field names; the beta surface moves.
2. **Read `./skill.md`** and walk the user through its Setup checklist step by step, then use its Gotchas and debugging table when something is off. It's written for exactly this.
3. **After the base app works, offer extensions.** Ask which (if any) they want, then edit `agents/spreadsheet-analyst.md` and run a bare `ant apply --yes`, which publishes the edit as a new version the next session picks up:
   - **Multiagent red-team pass**: add a `multiagent: { type: "coordinator", agents: [...] }` roster so the analyst hands its numbers to a toolless reviewer. The handoff events (`session.thread_created`, `agent.thread_message_sent/received`) already arrive on the stream; the reducer currently ignores them, so this needs a rendering branch too.
   - **Memory store**: attach `resources: [{ type: "memory_store", ... }]` at session create so the analyst remembers per-dataset conventions across chats.
   - **MCP connector**: add an `mcp_servers` entry plus an `mcp_toolset`. MCP tools default to `always_ask`, so they light up the same approval gate for free.
   - **`ask_user` human tool**: a custom tool whose card renders buttons and answers `user.custom_tool_result` from the click (assistant-ui `addResult`), instead of auto-answering like `show_chart`.

   Pull exact shapes from the `/claude-api` skill's `shared/managed-agents-*.md` docs.

## Commands

- `npm run dev` — the app on http://localhost:3000 (binds localhost only)
- `ant apply --yes agents environments` — one-time provisioning of the agent + environment into `claude-lock.json` (ant 1.30 or later; `--yes` because you have no terminal for its prompt; it needs `ant auth login` or an exported `ANTHROPIC_API_KEY` and does not read `.env`)
- `npm run typecheck` — `tsc --noEmit`
- `npm run lint` — eslint (the copy-in `components/` are ignored on purpose)
- `npm test` — the reducer's golden-turn test; run it whenever the event mapping changes

## Conventions

- Name the Anthropic SDK client `client` (`const client = new Anthropic()`), in code and in docs.
- Never use the "CMA" acronym. Write "Managed Agents" or "Claude Managed Agents", and spell it out in identifiers and file names.
- Every route under `app/api/sessions/[id]/` must pass the id through `ownedSession()` (`lib/owned-session.ts`) before touching the API. File downloads additionally check the file belongs to that session. Don't add a session-less file route.
- Keep `lib/managed-agents/reducer.ts` pure: no fetch, no React, no clocks. That's what keeps it testable and keeps replay identical to live.
- `components/assistant-ui/`, `components/ui/`, `hooks/`, and `lib/utils.ts` are assistant-ui copy-in components (`npx assistant-ui add ...`). Regenerate them rather than hand-editing; put quickstart UI in `components/tool-uis/` and `app/`.
