import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import Anthropic from "@anthropic-ai/sdk";

// The one Anthropic client for the whole server. `new Anthropic()` reads
// ANTHROPIC_API_KEY, and falls back to `ant auth login` CLI credentials when
// the variable is unset, so .env can carry no key at all.
export const client = new Anthropic();

// The agent and environment come from claude-lock.json at the project root,
// where `ant apply agents environments` records what it created. CLAUDE_AGENT_ID
// and CLAUDE_ENVIRONMENT_ID fill in only when that file has no entry (a host
// deployed without it), so IDs an older setup left in .env cannot point the app
// at stale resources. A value still holding its placeholder ("agent_...")
// counts as unset.
const LOCKFILE = join(process.cwd(), "claude-lock.json");

function lockfileId(file: string): string | undefined {
  if (!existsSync(LOCKFILE)) return undefined;
  const lock = JSON.parse(readFileSync(LOCKFILE, "utf8")) as {
    resources?: Record<string, { id?: string }>;
  };
  return lock.resources?.[file]?.id;
}

function resourceId(file: string, envName: string): string {
  const fromEnv = process.env[envName];
  const id = lockfileId(file) || (fromEnv && !fromEnv.endsWith("...") ? fromEnv : undefined);
  if (!id) {
    throw new Error(
      `No ${envName === "CLAUDE_AGENT_ID" ? "agent" : "environment"} ID. Run \`ant apply agents environments\` in this directory (it writes claude-lock.json), then restart \`npm run dev\`.`,
    );
  }
  return id;
}

export const agentId = () => resourceId("./agents/spreadsheet-analyst.md", "CLAUDE_AGENT_ID");
export const environmentId = () => resourceId("./environments/spreadsheet-analyst.yaml", "CLAUDE_ENVIRONMENT_ID");

// Sessions this quickstart creates are tagged; the app never lists or
// touches anything else, even though the API key can see the whole org.
export const SESSION_METADATA = { quickstart: "assistant-ui" } as const;

export { Anthropic };
