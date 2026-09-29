import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * The planner agent, environment, and vault this app runs sessions on: the
 * resources `ant apply` (run by ./agents/setup.sh) creates from agents/,
 * environments/, and vaults/ and records in claude-lock.json at the project
 * root. CLAUDE_AGENT_ID, CLAUDE_ENVIRONMENT_ID, and CLAUDE_VAULT_ID fill in
 * only where the lockfile has no entry (a host without the lockfile), so IDs
 * an older setup left in .env cannot point the app at archived resources.
 */
const LOCKFILE = join(process.cwd(), "claude-lock.json");

type Lockfile = { resources?: Record<string, { id?: string }> };

function readLockfile(): Lockfile | undefined {
  if (!existsSync(LOCKFILE)) return undefined;
  return JSON.parse(readFileSync(LOCKFILE, "utf8")) as Lockfile;
}

function resolve(file: string, envName: string): string {
  const id = readLockfile()?.resources?.[file]?.id || process.env[envName];
  if (!id) {
    throw new Error(
      `No ${envName.replace("CLAUDE_", "").replace("_ID", "").toLowerCase()} ID: run \`./agents/setup.sh\` (its \`ant apply\` writes claude-lock.json), then restart \`npm run dev\`.`,
    );
  }
  return id;
}

export const plannerAgentId = (): string => resolve("./agents/roadtrip-planner.md", "CLAUDE_AGENT_ID");
export const environmentId = (): string => resolve("./environments/roadtrip-planner.yaml", "CLAUDE_ENVIRONMENT_ID");
export const vaultId = (): string => resolve("./vaults/roadtrip-planner.yaml", "CLAUDE_VAULT_ID");
