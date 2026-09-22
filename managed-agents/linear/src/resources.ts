// The agent and environment this bridge runs sessions on: the two resources
// `ant apply agents environments` creates and records in claude-lock.json.
// CLAUDE_AGENT_ID and CLAUDE_ENVIRONMENT_ID fill in only where the lockfile has
// no entry: a deployed host without the lockfile, or an environment you reuse
// instead of creating (skill.md, "Debugging"). The lockfile wins otherwise, so
// IDs an older setup left in .env cannot point the bridge at a stale agent.
import { existsSync, readFileSync } from "node:fs";

const LOCKFILE = new URL("../claude-lock.json", import.meta.url);

const lock = existsSync(LOCKFILE)
  ? (JSON.parse(readFileSync(LOCKFILE, "utf8")) as { resources?: Record<string, { id?: string }> })
  : undefined;

function resolve(file: string, envName: string): { id: string | undefined; from: string } {
  const fromLock = lock?.resources?.[file]?.id;
  if (fromLock) return { id: fromLock, from: "claude-lock.json" };
  return { id: process.env[envName] || undefined, from: envName };
}

const agent = resolve("./agents/linear-assistant.md", "CLAUDE_AGENT_ID");
const environment = resolve("./environments/linear-assistant.yaml", "CLAUDE_ENVIRONMENT_ID");

export const AGENT_ID = agent.id;
export const ENVIRONMENT_ID = environment.id;

// One line at startup, so a bridge talking to the wrong agent is easy to spot.
export function describeResources(): string {
  return `agent ${agent.id} (from ${agent.from}), environment ${environment.id} (from ${environment.from})`;
}
