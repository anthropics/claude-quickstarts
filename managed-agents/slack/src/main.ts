import { handleSlackEvents } from "./slack-events";
import { handleManagedAgentsWebhook } from "./managed-agents-webhook";

const PORT = Number(process.env.PORT) || 3000;
const BASE_URL = process.env.BASE_URL || `http://localhost:${PORT}`;

for (const v of [
  "SLACK_SIGNING_SECRET",
  "SLACK_BOT_TOKEN",
  "ANTHROPIC_WEBHOOK_SIGNING_KEY",
  "CLAUDE_AGENT_ID",
  "CLAUDE_ENVIRONMENT_ID",
]) {
  if (!process.env[v]) {
    console.error(`FATAL: ${v} is required`);
    process.exit(1);
  }
}

Bun.serve({
  port: PORT,
  async fetch(req) {
    const url = new URL(req.url);

    if (url.pathname === "/" && req.method === "GET") {
      return Response.json({ status: "ok" });
    }
    // Slack → us (user @mentioned or DM'd the bot)
    if (url.pathname === "/slack/events" && req.method === "POST") {
      return handleSlackEvents(req);
    }
    // Anthropic → us (Claude session idled / terminated)
    if (url.pathname === "/managed-agents/webhook" && req.method === "POST") {
      return handleManagedAgentsWebhook(req);
    }
    return new Response("Not Found", { status: 404 });
  },
});

console.log(`Bridge running at ${BASE_URL}`);
console.log(`  Slack events:           ${BASE_URL}/slack/events`);
console.log(`  Managed Agents webhook: ${BASE_URL}/managed-agents/webhook`);
