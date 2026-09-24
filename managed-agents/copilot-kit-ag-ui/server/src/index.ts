/**
 * CopilotKit runtime hosting the managed-agent finance assistant.
 *
 * The browser's CopilotKitProvider talks to this endpoint; the runtime
 * dispatches each chat turn to a ManagedAgentsAgent from
 * @ag-ui/claude-managed-agents, which maps the AG-UI thread to a Claude
 * Managed Agents session and translates its events for CopilotKit.
 */
import express from 'express';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { CopilotSseRuntime } from '@copilotkit/runtime/v2';
import { createCopilotExpressHandler } from '@copilotkit/runtime/v2/express';
import {
  InMemorySessionStore,
  ManagedAgentsAgent,
  type SessionStore,
} from '@ag-ui/claude-managed-agents';
import { loadAgentIds } from './resources.ts';
import { vizTools } from './vizTools.ts';

const PORT = Number(process.env.PORT ?? 8787);

// Fail fast: a clear "run ant apply first" at boot beats a mid-chat error.
const ids = loadAgentIds();

// The default in-memory store, wrapped only to log each new session's Console
// trace URL — the raw event history (every tool call and thinking span) is
// worth watching next to the chat. `default` resolves to the session's actual
// workspace when Console loads.
const sessions = new InMemorySessionStore();
const store: SessionStore = {
  get: (key) => sessions.get(key),
  set: (key, record) => {
    if (sessions.get(key)?.sessionId !== record.sessionId) {
      console.log(
        `[session] ${record.sessionId}\n  trace: https://platform.claude.com/workspaces/default/sessions/${record.sessionId}`,
      );
    }
    sessions.set(key, record);
  },
  delete: (key) => sessions.delete(key),
};

const runtime = new CopilotSseRuntime({
  agents: {
    'financial-assistant': new ManagedAgentsAgent({
      managedAgentId: ids.agentId,
      agentVersion: ids.agentVersion,
      environmentId: ids.environmentId,
      backendTools: vizTools,
      sessionStore: store,
      sessionTitle: (threadId) => `Finance assistant thread ${threadId}`,
    }),
  },
});

// Unset: permissive CORS (fine locally). On a public deployment, set
// ALLOWED_ORIGINS to your frontend's origin(s), comma-separated: this
// endpoint spends your API credits. Set-but-empty means deny cross-origin.
const allowedOrigins = process.env.ALLOWED_ORIGINS?.split(',')
  .map((o) => o.trim())
  .filter(Boolean);

const app = express();
app.use(
  createCopilotExpressHandler({
    runtime,
    basePath: '/api/copilotkit',
    cors: allowedOrigins ? { origin: allowedOrigins } : true,
  }),
);

// Single-process deploys: after `npm run build`, serve the built frontend
// from the same port as the runtime. Absent in dev, where Vite serves it.
const here = path.dirname(fileURLToPath(import.meta.url));
const webDist = path.resolve(here, '../../web/dist');
if (fs.existsSync(webDist)) {
  app.use(express.static(webDist));
  console.log(`Serving web/dist as the frontend`);
}

app.listen(PORT, () => {
  console.log(`CopilotKit runtime listening on http://localhost:${PORT}/api/copilotkit`);
  console.log(`  agent ${ids.agentId} v${ids.agentVersion}, environment ${ids.environmentId}`);
});
