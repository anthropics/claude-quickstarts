// The agent and environment this bridge runs sessions on: the two resources
// `ant apply agents environments` creates and records in claude-lock.json.
// CLAUDE_AGENT_ID and CLAUDE_ENVIRONMENT_ID override the lockfile, for a
// deployed host that sets them as config instead.
import { existsSync, readFileSync } from "node:fs";

const LOCKFILE = new URL("../claude-lock.json", import.meta.url);

function lockfileId(file: string): string | undefined {
  if (!existsSync(LOCKFILE)) return undefined;
  const lock = JSON.parse(readFileSync(LOCKFILE, "utf8")) as {
    resources?: Record<string, { id?: string }>;
  };
  return lock.resources?.[file]?.id;
}

export const AGENT_ID = process.env.CLAUDE_AGENT_ID || lockfileId("./agents/linear-assistant.md");
export const ENVIRONMENT_ID =
  process.env.CLAUDE_ENVIRONMENT_ID || lockfileId("./environments/linear-assistant.yaml");
