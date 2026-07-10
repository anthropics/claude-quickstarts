// Push the current agent-config.ts (name, model, system prompt) onto the
// existing agent as a new version. Use this after editing the config --
// re-running create-agent.ts would provision a duplicate. Running sessions
// keep their pinned version; new chats pick up the latest.

import Anthropic from "@anthropic-ai/sdk";
import { AGENT_DESCRIPTION, AGENT_NAME, MODEL, SYSTEM_PROMPT } from "./agent-config";

const agentId = process.env.CLAUDE_AGENT_ID;
if (!agentId || agentId.endsWith("...")) {
  console.error("CLAUDE_AGENT_ID is not set. Run `npm run setup` first and fill in .env.");
  process.exit(1);
}

const client = new Anthropic();

// Updates take the current version (optimistic concurrency) and return the
// new one. Sessions already running keep the version they started with.
const current = await client.beta.agents.retrieve(agentId);
const agent = await client.beta.agents.update(agentId, {
  version: current.version,
  name: AGENT_NAME,
  description: AGENT_DESCRIPTION,
  model: MODEL,
  system: SYSTEM_PROMPT,
});
console.log(`${agent.name}: version ${current.version} -> ${agent.version} (${MODEL})`);
