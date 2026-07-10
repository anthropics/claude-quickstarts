// One-time provisioning: create the agent and the environment, then copy the
// printed IDs into .env. Never call this in the request path -- agents are
// persistent, versioned resources (see skill.md).

import Anthropic from "@anthropic-ai/sdk";
import { AGENT_DESCRIPTION, AGENT_NAME, MODEL, SYSTEM_PROMPT } from "./agent-config";

for (const name of ["CLAUDE_AGENT_ID", "CLAUDE_ENVIRONMENT_ID"]) {
  const value = process.env[name];
  if (value && !value.endsWith("...")) {
    console.error(
      `${name} is already set (${value}). This quickstart needs exactly one copy of each ` +
        `resource. To push config changes onto the existing agent, run \`npm run update-agent\`; ` +
        `unset the .env entry only if you really want to re-provision.`,
    );
    process.exit(1);
  }
}

const client = new Anthropic();

// Tags every resource so it stays findable in the Console even if this
// script dies between creates. Each ID also prints as soon as its resource
// exists, for the same reason.
const metadata = { quickstart: "chat-sdk" };

const environment = await client.beta.environments.create({
  name: "quickstart-chat-research-analyst-env",
  config: {
    type: "cloud",
    // Unrestricted egress: the analyst fetches arbitrary web pages, and the
    // sandbox holds no secrets and no bash (see the tool config below), so
    // there is nothing for a hostile page to steal or run.
    networking: { type: "unrestricted" },
  },
  metadata,
});
console.log(`environment: ${environment.id}`);

const agent = await client.beta.agents.create({
  name: AGENT_NAME,
  description: AGENT_DESCRIPTION,
  model: MODEL,
  system: SYSTEM_PROMPT,
  tools: [
    {
      type: "agent_toolset_20260401",
      // always_allow because this chat UI has no human-approval surface -- an
      // always_ask tool would park the session waiting for a confirmation
      // that can never arrive.
      default_config: { enabled: true, permission_policy: { type: "always_allow" } },
      // Bash stays off: this agent reads untrusted web pages, and
      // prompt-injected content plus auto-approved shell plus open egress is
      // an exfiltration path. The brief is web research and synthesis; it
      // does not need a shell.
      configs: [{ name: "bash", enabled: false }],
    },
  ],
  metadata,
});
console.log(`analyst:     ${agent.id} (version ${agent.version}, ${MODEL})`);

console.log("\nAdd to .env:");
console.log(`CLAUDE_AGENT_ID=${agent.id}`);
console.log(`CLAUDE_ENVIRONMENT_ID=${environment.id}`);
