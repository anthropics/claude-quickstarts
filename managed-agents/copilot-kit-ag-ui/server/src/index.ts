/**
 * CopilotKit runtime hosting the managed-agent financial advisor.
 *
 * The browser's CopilotKitProvider talks to this endpoint; the runtime
 * dispatches each chat turn to the AG-UI agent in agent.ts, which drives a
 * Claude Managed Agents session (see bridge.ts for the event translation).
 */
import express from 'express';
import { CopilotSseRuntime } from '@copilotkit/runtime/v2';
import { createCopilotExpressHandler } from '@copilotkit/runtime/v2/express';
import { ManagedAgentFinancialAdvisor } from './agent.ts';
import { loadAgentIds } from './setup.ts';

const PORT = Number(process.env.PORT ?? 8787);

// Fail fast: a clear "run npm run setup first" at boot beats a mid-chat error.
loadAgentIds();

// Demo hardening: a stray rejection from an abandoned upstream stream must
// not take the whole server down — log loudly and keep serving. Synchronous
// exceptions still crash the process, as they should.
process.on('unhandledRejection', (reason) => {
  console.error('[fatal-averted] unhandled rejection:', reason);
});

const runtime = new CopilotSseRuntime({
  agents: {
    'financial-advisor': new ManagedAgentFinancialAdvisor(),
  },
});

const app = express();
app.use(
  createCopilotExpressHandler({
    runtime,
    basePath: '/api/copilotkit',
  }),
);

app.listen(PORT, () => {
  console.log(`CopilotKit runtime listening on http://localhost:${PORT}/api/copilotkit`);
});
