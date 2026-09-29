# CLAUDE.md

A finance assistant chat app wiring a Claude Managed Agent to CopilotKit's self-hosted runtime over the AG-UI protocol. This file is the technical map: architecture, where the code is, design notes, and how to walk a user through setup.

## Architecture

```
browser (Vite + React)               server (Express)                   Anthropic
┌────────────────────┐  runtime API  ┌─────────────────┐  user.message  ┌──────────────────┐
│ CopilotKitProvider │ ────────────▶ │ CopilotSse-     │ ─────────────▶ │ Managed Agents   │
│  └─ CopilotChat    │               │  Runtime        │                │  session         │
│                    │  AG-UI events │  └─ ManagedAgents│  SSE w/ live  │  └─ financial-   │
│                    │ ◀──────────── │     Agent       │ ◀───────────── │     assistant    │
└────────────────────┘               └─────────────────┘   previews     └──────────────────┘
```

Four pieces:

1. **A Claude Managed Agent.** One `financial-assistant` agent on `claude-fable-5` with the built-in toolset (bash, files, web search), so it can pull current rates and run real calculations in its own workspace. Anthropic hosts the agent loop and the container. Sessions keep the conversation state server-side, so each run only sends the newest user message.
2. **The upstream AG-UI adapter.** [`@ag-ui/claude-managed-agents`](https://www.npmjs.com/package/@ag-ui/claude-managed-agents) does the whole Managed Agents ↔ AG-UI translation: one AG-UI thread per managed session, live text previews via event delta streaming, tool activity as `TOOL_CALL_*` events, thinking as `REASONING_*` events, interrupts on disconnect, and a per-turn time cap. This repo contains no bridge code of its own.
3. **CopilotKit for the UI.** The adapter's `ManagedAgentsAgent` is a plain AG-UI `AbstractAgent`, registered in a self-hosted `CopilotSseRuntime` and rendered with the stock `CopilotChat` component. No custom chat code.
4. **Generative UI.** Four visual tools (payoff timeline, growth projection, budget breakdown, scenario comparison) are passed to the adapter as `backendTools`; it registers them on each session, streams every call to the browser as `TOOL_CALL_*` events, and posts the handler's ack back so the turn keeps flowing. CopilotKit's `useRenderTool` mounts an interactive React component inline in the chat, with sliders that recompute the charts client-side.

## Where the interesting code is

| File | What it shows |
| --- | --- |
| `agents/financial-assistant.md`, `environments/financial-assistant.yaml` | The agent (frontmatter is the configuration, prose is the system prompt) and its container, as files for `ant apply` |
| `server/src/resources.ts` | `loadAgentIds()`: the agent (with version) and environment from `claude-lock.json`, or from `ANTHROPIC_ENVIRONMENT_ID`/`ANTHROPIC_AGENT_ID`/`ANTHROPIC_AGENT_VERSION` when the lockfile is absent |
| `server/src/index.ts` | The whole integration: a `ManagedAgentsAgent` in a self-hosted `CopilotSseRuntime` on Express, CORS from `ALLOWED_ORIGINS`, static serving of `web/dist` when built |
| `server/src/vizTools.ts` | The generative-UI tool contracts the agent sees, as the adapter's `backendTools` |
| `web/src/viz/renderers.tsx` | `useRenderTool` registrations mapping tool calls to React components |
| `web/src/viz/` | The interactive visuals: SVG charts, sliders, client-side finance math |
| `web/src/App.tsx` | The frontend: `CopilotKitProvider` + `CopilotChat` + viz renderers |

## Commands

- `npm install`, then `ant apply --yes agents environments` once (ant 1.30 or later; `--yes` because you have no terminal for its confirmation prompt), then `npm run dev` (server on :8787, web on :5173). After editing `agents/financial-assistant.md`, a bare `ant apply --yes` publishes the new version; restart the server to pin it.
- `npm run build` builds the frontend to `web/dist`. `npm start` runs the server without watch and serves `web/dist` if present.
- `npm run typecheck` covers both workspaces. There are no tests. Verify changes by running the app.

## Design notes

- `package.json` pins one `rxjs` version via `overrides` so the whole workspace shares a single copy: the AG-UI client and the CopilotKit runtime exchange RxJS observables, and two copies in the tree can break `instanceof` checks.
- The visual tools are render-only: their result is the rendering itself, so each `backendTools` handler ignores its input and returns a "rendered to the user" ack. The agent supplies starting numbers, and the sliders recompute everything client-side without another agent turn.
- The visual tools live only in `server/src/vizTools.ts` — `agents/financial-assistant.md` does not put them on the agent. The adapter registers them on each session as tool overrides (merged with the agent's own toolset), so changing a tool contract never requires re-provisioning.
- The adapter also emits `TOOL_CALL_*` events for built-in tool use (web_search, bash, file ops). The wildcard `useRenderTool` registration in `web/src/viz/renderers.tsx` renders each as a compact expandable activity row (`ToolActivity`).
- CopilotKit's runtime delivers tool args in version-dependent shapes: a typed object, an object with every number stringified, or one whose nested arrays arrive as JSON strings. `web/src/viz/renderers.tsx` normalizes the structure and parses args through coercing zod schemas before mounting a component — blind-spreading `props.parameters` breaks silently when the wire format shifts.
- The agent's system prompt tells it to call visual tools directly, never from inside repl scripts: a repl-wrapped custom tool call parks the session on the repl call itself, a state the adapter (0.0.1) reads as unanswerable and interrupts. Drop that prompt line once the adapter handles repl suspension.
- The thread-to-session store is the adapter's bounded in-memory default, wrapped in `index.ts` only to log each new session's Console trace URL. A server restart starts fresh sessions, and old ones are not deleted. Fine for a demo, not for production; the adapter accepts a persistent `sessionStore` when it matters.

## Walking a user through setup

When the user asks to be walked through setting up this demo, go step by step, run the commands for them where possible, and check each result before moving on:

1. **Node version.** `node --version` must be 22 or newer.
2. **Credentials.** Either `ANTHROPIC_API_KEY` is set or an `ant auth login` profile exists. The account needs the Managed Agents beta, and `claude-fable-5` needs 30-day data retention on the org (not available under zero data retention).
3. **Install.** `npm install` from this directory (it is an npm workspace root).
4. **Provision.** `ant apply --yes agents environments`. This creates the cloud environment and the agent from `environments/` and `agents/` and writes their IDs to `claude-lock.json`. Re-running changes nothing until a file changes. It needs `ant auth login` or an exported `ANTHROPIC_API_KEY`; it does not read `.env`. If it prints `refusing to apply`, a resource was changed or archived in the Console: show the user the reason before reaching for `--force`.
5. **Run.** `npm run dev`, then open http://localhost:5173 and suggest a first prompt, for example: "If I invest $500/month at a 7% annual return, what will I have in 20 years?" Point out the Console trace URL the server logs per session.

Common failures:

- `No agent configured` at server boot: `ant apply agents environments` has not run in this directory (no `claude-lock.json` here), and the three `ANTHROPIC_*` ID env vars are not set.
- 403/404 from `ant apply`: the org lacks Managed Agents beta access, or the model is unavailable under the org's data retention policy. A 409 on the environment means `quickstart-copilot-kit-financial-assistant-env` already exists in the workspace: change `name` in `environments/financial-assistant.yaml`.
- `instanceof` errors mentioning Observable: duplicate `rxjs` copies. Reinstall from the workspace root so the `overrides` pin applies.
- Port conflicts: set `PORT` for the server, and in dev also update the proxy target in `web/vite.config.ts`, which points at :8787. Vite picks the next free port on its own, but then the printed URL changes.
- Chat errors in the browser with a healthy web server: check the server logs on :8787. The Vite dev proxy forwards `/api/copilotkit` there.
