# Financial advisor: Claude Managed Agents × CopilotKit

A minimal chat app wiring three things together:

1. **A Claude Managed Agent.** One `financial-advisor` agent on
   `claude-fable-5` with the built-in toolset (bash, files, web search), so it
   can pull current rates and run real calculations in its own workspace.
   Anthropic hosts the agent loop and the container; sessions keep the
   conversation state server-side.
2. **Event delta streaming** in the Anthropic TypeScript SDK. The bridge opts
   into live previews (`event_deltas: ['agent.message', 'agent.thinking']`) on
   the session event stream and reconciles them with the SDK's
   `accumulateManagedAgentsEvent` helper, so replies reach the browser token
   by token instead of turn by turn.
3. **[CopilotKit](https://docs.copilotkit.ai)** for the UI. The agent is a
   plain AG-UI `AbstractAgent`, registered in a self-hosted `CopilotSseRuntime`
   and rendered with the stock `CopilotChat` component. No custom chat code.
4. **Generative UI.** The agent has four visual tools (payoff timeline, growth
   projection, budget breakdown, scenario comparison) declared as managed-agent
   custom tools. When it calls one, the bridge forwards the call as AG-UI
   `TOOL_CALL_*` events and immediately acks the session; CopilotKit's
   `useRenderTool` mounts an interactive React component inline in the chat,
   with sliders that recompute the charts client-side ("what if I paid $600
   instead").

```
browser (Vite + React)               server (Express)                   Anthropic
┌────────────────────┐  runtime API  ┌─────────────────┐  user.message  ┌──────────────────┐
│ CopilotKitProvider │ ────────────▶ │ CopilotSse-     │ ─────────────▶ │ Managed Agents   │
│  └─ CopilotChat    │               │  Runtime        │                │  session         │
│                    │  AG-UI events │  └─ AbstractAgent│  SSE w/ live  │  └─ financial-   │
│                    │ ◀──────────── │     (bridge.ts) │ ◀───────────── │     advisor      │
└────────────────────┘               └─────────────────┘   previews     └──────────────────┘
```

## Run it

Requires Node 22+, and Anthropic API credentials with the Managed Agents beta.
Either `ANTHROPIC_API_KEY` or an `ant auth login` profile works; the SDK finds
both on its own. Note that `claude-fable-5` requires 30-day data retention on
the org (not available under zero data retention).

```sh
npm install

# One time: create the environment + the agent, store IDs in agent-ids.json.
# Agents are persistent, versioned resources: created once, referenced by ID
# on every session. Re-run with `-- --force` to re-provision.
npm run setup

# Start the CopilotKit runtime (:8787) and the web app (:5173)
npm run dev
```

Open http://localhost:5173 and ask something like:

> If I invest $500/month at a 7% annual return, what will I have in 20 years?

Follow-ups work naturally: the CopilotKit thread maps to one managed session,
so the agent remembers the conversation. The server logs a Console trace URL
per session so you can watch the raw agent activity side by side.

## Where the interesting code is

| File | What it shows |
| --- | --- |
| `server/src/setup.ts` | Agent-first provisioning: environment + one agent with the built-in toolset |
| `server/src/agent.ts` | The whole CopilotKit integration: an AG-UI `AbstractAgent` whose `run()` is one managed-session turn |
| `server/src/bridge.ts` | Event translation: live previews to AG-UI text deltas, built-in tool activity to `TOOL_CALL_*`, the `requires_action` idle gate |
| `server/src/index.ts` | Self-hosted `CopilotSseRuntime` on Express via `createCopilotExpressHandler` |
| `server/src/vizTools.ts` | The generative-UI tool contracts the agent sees |
| `web/src/viz/renderers.tsx` | `useRenderTool` registrations mapping tool calls to React components |
| `web/src/viz/` | The interactive visuals: SVG charts, sliders, client-side finance math |
| `web/src/App.tsx` | The frontend: `CopilotKitProvider` + `CopilotChat` + viz renderers |

## Notes

- `package.json` pins one `rxjs` version via `overrides` so the whole
  workspace shares a single copy: the AG-UI client and the CopilotKit runtime
  exchange RxJS observables, and two copies in the tree can break
  `instanceof` checks.
- CopilotKit's runtime clones registered agents per run, so the agent class
  keeps no instance state; the Anthropic client is a module-level singleton
  and per-thread state lives in `sessions.ts`.
- Event delta streaming is best-effort by design: the bridge tracks what the
  previews delivered and tops up from the buffered `agent.message`, which is
  always canonical.
- The visual tools are render-only: their result is the rendering itself, so
  the bridge acks each call server-side ("rendered to the user") the moment it
  arrives, and the `requires_action` idle that follows an acked call is
  expected rather than treated as a hang. The agent supplies starting numbers;
  the sliders recompute everything client-side without another agent turn.
- The bridge also emits `TOOL_CALL_*` events for built-in tool use
  (web_search, bash, file ops). The wildcard `useRenderTool` registration in
  `web/src/viz/renderers.tsx` renders each as a compact expandable activity
  row (`ToolActivity`).
- The thread-to-session registry is in memory: a server restart starts fresh
  sessions, and old ones are not deleted. Fine for a demo, not for production.
