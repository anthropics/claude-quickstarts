# CLAUDE.md

A finance assistant chat app wiring a Claude Managed Agent to CopilotKit's self-hosted runtime over the AG-UI protocol. This file is the technical map: architecture, where the code is, design notes, and how to walk a user through setup.

## Architecture

```
browser (Vite + React)               server (Express)                   Anthropic
┌────────────────────┐  runtime API  ┌─────────────────┐  user.message  ┌──────────────────┐
│ CopilotKitProvider │ ────────────▶ │ CopilotSse-     │ ─────────────▶ │ Managed Agents   │
│  └─ CopilotChat    │               │  Runtime        │                │  session         │
│                    │  AG-UI events │  └─ AbstractAgent│  SSE w/ live  │  └─ financial-   │
│                    │ ◀──────────── │     (bridge.ts) │ ◀───────────── │     assistant    │
└────────────────────┘               └─────────────────┘   previews     └──────────────────┘
```

Four pieces:

1. **A Claude Managed Agent.** One `financial-assistant` agent on `claude-fable-5` with the built-in toolset (bash, files, web search), so it can pull current rates and run real calculations in its own workspace. Anthropic hosts the agent loop and the container. Sessions keep the conversation state server-side, so each run only sends the newest user message.
2. **Event delta streaming.** The bridge opts into live previews (`event_deltas: ['agent.message', 'agent.thinking']`) on the session event stream and reconciles them with the SDK's `accumulateManagedAgentsEvent` helper, so replies reach the browser token by token instead of turn by turn.
3. **CopilotKit for the UI.** The agent is a plain AG-UI `AbstractAgent`, registered in a self-hosted `CopilotSseRuntime` and rendered with the stock `CopilotChat` component. No custom chat code.
4. **Generative UI.** The agent has four visual tools (payoff timeline, growth projection, budget breakdown, scenario comparison) declared as managed-agent custom tools. When it calls one, the bridge forwards the call as AG-UI `TOOL_CALL_*` events and immediately acks the session. CopilotKit's `useRenderTool` mounts an interactive React component inline in the chat, with sliders that recompute the charts client-side.

## Where the interesting code is

| File | What it shows |
| --- | --- |
| `server/src/setup.ts` | Agent-first provisioning: environment + one agent with the built-in toolset. Also `loadAgentIds()`, which prefers `ANTHROPIC_ENVIRONMENT_ID`/`ANTHROPIC_AGENT_ID`/`ANTHROPIC_AGENT_VERSION` env vars over `agent-ids.json` |
| `server/src/agent.ts` | The whole CopilotKit integration: an AG-UI `AbstractAgent` whose `run()` is one managed-session turn |
| `server/src/bridge.ts` | Event translation: live previews to AG-UI text deltas, built-in tool activity to `TOOL_CALL_*`, the `requires_action` idle gate |
| `server/src/index.ts` | Self-hosted `CopilotSseRuntime` on Express, CORS from `ALLOWED_ORIGINS`, static serving of `web/dist` when built |
| `server/src/sessions.ts` | In-memory thread-to-session registry |
| `server/src/vizTools.ts` | The generative-UI tool contracts the agent sees |
| `web/src/viz/renderers.tsx` | `useRenderTool` registrations mapping tool calls to React components |
| `web/src/viz/` | The interactive visuals: SVG charts, sliders, client-side finance math |
| `web/src/App.tsx` | The frontend: `CopilotKitProvider` + `CopilotChat` + viz renderers |

## Commands

- `npm install`, then `npm run setup` once, then `npm run dev` (server on :8787, web on :5173).
- `npm run build` builds the frontend to `web/dist`. `npm start` runs the server without watch and serves `web/dist` if present.
- `npm run typecheck` covers both workspaces. There are no tests. Verify changes by running the app.

## Design notes

- `package.json` pins one `rxjs` version via `overrides` so the whole workspace shares a single copy: the AG-UI client and the CopilotKit runtime exchange RxJS observables, and two copies in the tree can break `instanceof` checks.
- CopilotKit's runtime clones registered agents per run, so the agent class keeps no instance state. The Anthropic client is a module-level singleton and per-thread state lives in `sessions.ts`.
- Event delta streaming is best-effort by design: the bridge tracks what the previews delivered and tops up from the buffered `agent.message`, which is always canonical.
- The visual tools are render-only: their result is the rendering itself, so the bridge acks each call server-side ("rendered to the user") the moment it arrives, and the `requires_action` idle that follows an acked call is expected rather than treated as a hang. The agent supplies starting numbers, and the sliders recompute everything client-side without another agent turn.
- The bridge also emits `TOOL_CALL_*` events for built-in tool use (web_search, bash, file ops). The wildcard `useRenderTool` registration in `web/src/viz/renderers.tsx` renders each as a compact expandable activity row (`ToolActivity`).
- The thread-to-session registry is in memory: a server restart starts fresh sessions, and old ones are not deleted. Fine for a demo, not for production.
- The SDK stream reports aborts as a clean end of stream, so the bridge re-checks the abort signal after the stream ends (see `bridge.ts`).

## Walking a user through setup

When the user asks to be walked through setting up this demo, go step by step, run the commands for them where possible, and check each result before moving on:

1. **Node version.** `node --version` must be 22 or newer.
2. **Credentials.** Either `ANTHROPIC_API_KEY` is set or an `ant auth login` profile exists. The account needs the Managed Agents beta, and `claude-fable-5` needs 30-day data retention on the org (not available under zero data retention).
3. **Install.** `npm install` from this directory (it is an npm workspace root).
4. **Provision.** `npm run setup`. This creates a cloud environment and the agent once, and writes their IDs to `agent-ids.json`. Re-running is a no-op unless `-- --force` is passed.
5. **Run.** `npm run dev`, then open http://localhost:5173 and suggest a first prompt, for example: "If I invest $500/month at a 7% annual return, what will I have in 20 years?" Point out the Console trace URL the server logs per session.

Common failures:

- `No agent configured` at server boot: `npm run setup` was not run, and the three `ANTHROPIC_*` ID env vars are not set.
- 403/404 from `client.beta.environments.create` or `client.beta.agents.create` during setup: the org lacks Managed Agents beta access, or the model is unavailable under the org's data retention policy.
- `instanceof` errors mentioning Observable: duplicate `rxjs` copies. Reinstall from the workspace root so the `overrides` pin applies.
- Port conflicts: set `PORT` for the server, and in dev also update the proxy target in `web/vite.config.ts`, which points at :8787. Vite picks the next free port on its own, but then the printed URL changes.
- Chat errors in the browser with a healthy web server: check the server logs on :8787. The Vite dev proxy forwards `/api/copilotkit` there.
