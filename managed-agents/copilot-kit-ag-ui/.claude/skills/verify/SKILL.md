---
name: verify
description: Build and drive the copilot-kit-ag-ui demo to verify changes end-to-end.
---

# Verifying changes to this demo

Build and drive the real server. `npm run typecheck` is CI's job, not evidence.

## Without Anthropic credentials or provisioned agents

The server boots and serves everything except a live agent turn with stub IDs:

```sh
npm install && npm run build
ANTHROPIC_API_KEY=sk-ant-test ANTHROPIC_ENVIRONMENT_ID=env_x \
  ANTHROPIC_AGENT_ID=agent_x ANTHROPIC_AGENT_VERSION=1 PORT=8799 npm start
```

Probes that exercise the wiring:

- `GET :8799/` returns the built `web/dist/index.html` (there is no SPA catch-all, so unknown paths 404).
- `GET :8799/api/copilotkit/info` lists the registered agents, confirming agent id and class registration without an API call.
- `POST :8799/api/copilotkit/agent/financial-assistant/run` with an AG-UI body (`{"threadId":"t1","runId":"r1","messages":[{"id":"m1","role":"user","content":"hi"}],"state":{},"tools":[],"context":[],"forwardedProps":{}}`) reaches sessions.ts and fails with a 401 from Anthropic. That 401 in the SSE `RUN_ERROR` proves the full route-to-SDK path.
- CORS: send `OPTIONS` with an `Origin` header. With `ALLOWED_ORIGINS` set, allowed origins get `Access-Control-Allow-Origin` echoed and others get none.
- `VITE_COPILOT_RUNTIME_URL=... npm run build` then grep `web/dist/assets` for the URL to confirm build-time baking.

## With real credentials

`npm run setup` once, `npm run dev`, open http://localhost:5173, send a prompt that triggers a visual tool ("show me a growth projection for $500/month at 7%") and confirm the chart renders inline.

## Gotchas

- Boot requires agent identity: either `agent-ids.json` (from `npm run setup`) or the three `ANTHROPIC_*` ID env vars. Missing both is a deliberate boot failure.
- Static serving only activates when `web/dist` exists, so run `npm run build` before `npm start` probes.
