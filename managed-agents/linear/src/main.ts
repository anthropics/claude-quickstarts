import { LinearWebhookClient } from "@linear/sdk/webhooks";
import { handleOAuthAuthorize, handleOAuthCallback, isAllowedOrg } from "./oauth";
import { handleStop, isStopSignal, kickoffAgentSession } from "./agent";
import { handleManagedAgentsWebhook } from "./managed-agents-webhook";
import { AGENT_ID, ENVIRONMENT_ID } from "./resources";

const PORT = Number(process.env.PORT) || 3000;
const BASE_URL = process.env.BASE_URL || `http://localhost:${PORT}`;

for (const v of [
  "LINEAR_CLIENT_ID",
  "LINEAR_CLIENT_SECRET",
  "LINEAR_WEBHOOK_SIGNING_SECRET",
  "ANTHROPIC_WEBHOOK_SIGNING_KEY",
]) {
  if (!process.env[v]) {
    console.error(`FATAL: ${v} is required`);
    process.exit(1);
  }
}
if (!AGENT_ID || !ENVIRONMENT_ID) {
  console.error(
    "FATAL: no agent or environment ID. Run `ant apply agents environments` in this directory (it writes claude-lock.json), " +
      "or set CLAUDE_AGENT_ID and CLAUDE_ENVIRONMENT_ID.",
  );
  process.exit(1);
}

const linearHandler = new LinearWebhookClient(
  process.env.LINEAR_WEBHOOK_SIGNING_SECRET!,
).createHandler();

linearHandler.on("AgentSessionEvent", (event) => {
  if (!isAllowedOrg(event.organizationId)) {
    console.warn(`[linear] ignored event from org ${event.organizationId} (see LINEAR_ALLOWED_ORG_IDS)`);
    return;
  }
  console.log(`[linear] ${event.action} session=${event.agentSession.id}`);
  if (isStopSignal(event)) {
    handleStop(event).catch((err) => console.error("[linear] stop error:", err));
    return;
  }
  kickoffAgentSession(event).catch((err) =>
    console.error("[linear] kickoff error:", err),
  );
});

Bun.serve({
  port: PORT,
  async fetch(req) {
    const url = new URL(req.url);

    if (url.pathname === "/" && req.method === "GET") {
      return Response.json({ status: "ok" });
    }
    if (url.pathname === "/oauth/authorize" && req.method === "GET") {
      return handleOAuthAuthorize();
    }
    if (url.pathname === "/oauth/callback" && req.method === "GET") {
      return handleOAuthCallback(url);
    }
    // Linear → us (the agent was @mentioned or assigned)
    if (url.pathname === "/linear-webhook" && req.method === "POST") {
      return linearHandler(req);
    }
    // Anthropic → us (Claude session idled / terminated)
    if (url.pathname === "/managed-agents/webhook" && req.method === "POST") {
      return handleManagedAgentsWebhook(req);
    }
    return new Response("Not Found", { status: 404 });
  },
});

console.log(`Bridge running at ${BASE_URL}`);
console.log(`  Install agent:          ${BASE_URL}/oauth/authorize`);
console.log(`  Linear webhook:         ${BASE_URL}/linear-webhook`);
console.log(`  Managed Agents webhook: ${BASE_URL}/managed-agents/webhook`);
