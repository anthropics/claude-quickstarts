// One-time provisioning: creates the environment (sandbox template) and the
// agent (model + prompt + tools), then prints the IDs to paste into .env.
//
//   npm run setup
//
// The agent and environment are durable resources you reuse across every
// session, so this script refuses to run if IDs are already set. To rebuild
// from scratch, unset them in .env first (and archive the old ones in the
// Console or with the snippet in skill.md).

import Anthropic from "@anthropic-ai/sdk";
import {
  AGENT_NAME,
  ENVIRONMENT_CONFIG,
  METADATA,
  MODEL,
  SYSTEM_PROMPT,
  TOOLS,
} from "./agent-config";

for (const name of ["CLAUDE_AGENT_ID", "CLAUDE_ENVIRONMENT_ID"]) {
  const value = process.env[name];
  if (value && !value.endsWith("...")) {
    console.error(
      `${name} is already set (${value}). Provisioning again would orphan the existing resources.\n` +
        `Unset it in .env if you really want to re-provision.`,
    );
    process.exit(1);
  }
}

const client = new Anthropic();

// The environment is the sandbox template every session boots from: cloud
// container, open networking (web_search needs it), pandas preinstalled.
const environment = await client.beta.environments.create({
  name: "quickstart-spreadsheet-analyst-env",
  config: ENVIRONMENT_CONFIG,
  metadata: METADATA,
});
console.log(`environment: ${environment.id}`);

const agent = await client.beta.agents.create({
  name: AGENT_NAME,
  model: MODEL,
  system: SYSTEM_PROMPT,
  tools: TOOLS,
  // anthropic_cookbook tells Anthropic which quickstart this agent came from.
  // Safe to remove.
  metadata: { ...METADATA, anthropic_cookbook: "claude-quickstarts/assistant-ui" },
});
console.log(`agent:       ${agent.id} (version ${agent.version}, ${MODEL})`);

console.log("\nAdd to .env:");
console.log(`CLAUDE_AGENT_ID=${agent.id}`);
console.log(`CLAUDE_ENVIRONMENT_ID=${environment.id}`);
