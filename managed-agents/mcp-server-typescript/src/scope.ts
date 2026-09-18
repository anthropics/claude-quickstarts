// Every tool handler goes through this module. The MCP client is a model, so
// every ID it sends is untrusted text, and the server's Anthropic credentials
// can see every agent and session in the workspace. Two jobs:
//   1. Validate the shape of an ID before it becomes a URL path segment.
//   2. When ALLOWED_AGENT_IDS is set, refuse anything outside that set.
import Anthropic from "@anthropic-ai/sdk";

export const AGENT_ID = /^agent_[A-Za-z0-9]+$/;
export const SESSION_ID = /^sesn_[A-Za-z0-9]+$/;
export const EVENT_ID = /^sevt_[A-Za-z0-9]+$/;

/** A refusal that is safe to show the calling model. It never says whether the ID exists. */
export class ScopeError extends Error {}

const NOT_AVAILABLE = "That agent or session is not available through this server.";

function parseAllowlist(raw: string | undefined): Set<string> | null {
  const ids = (raw ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (ids.length === 0) return null;
  for (const id of ids) {
    if (!AGENT_ID.test(id)) {
      // Fail at startup. A typo that silently matched nothing would look like
      // a working allowlist.
      throw new Error("ALLOWED_AGENT_IDS has an entry that is not an agent ID (agent_...)");
    }
  }
  return new Set(ids);
}

/** null means no allowlist: every agent in the workspace is reachable. */
export const allowedAgentIds = parseAllowlist(process.env.ALLOWED_AGENT_IDS);

export function parseAgentId(value: string): string {
  if (!AGENT_ID.test(value)) throw new ScopeError("agent_id must look like agent_...");
  return value;
}

export function parseSessionId(value: string): string {
  if (!SESSION_ID.test(value)) throw new ScopeError("session_id must look like sesn_...");
  return value;
}

export function parseEventId(value: string): string {
  if (!EVENT_ID.test(value)) throw new ScopeError("after_id must look like sevt_...");
  return value;
}

export function assertAgentAllowed(agentId: string): string {
  const id = parseAgentId(agentId);
  if (allowedAgentIds && !allowedAgentIds.has(id)) throw new ScopeError(NOT_AVAILABLE);
  return id;
}

/**
 * Validate a session ID and, when an allowlist is set, confirm the session
 * belongs to an allowed agent. This runs BEFORE any side effect (send,
 * interrupt, archive, stream). A session's agent cannot change, so one check
 * per tool call is enough.
 */
export async function resolveAllowedSession(client: Anthropic, sessionId: string): Promise<string> {
  const id = parseSessionId(sessionId);
  if (!allowedAgentIds) return id;
  let agentId: string;
  try {
    agentId = (await client.beta.sessions.retrieve(id)).agent.id;
  } catch (err) {
    // The API answers 400 for an ID it has never seen, and 403 or 404 for one
    // these credentials cannot read. All three get the same refusal as a
    // session that exists but belongs to another agent, so the answer does not
    // reveal which IDs are real.
    if (err instanceof Anthropic.APIError && [400, 403, 404].includes(err.status ?? 0)) {
      throw new ScopeError(NOT_AVAILABLE);
    }
    throw err;
  }
  if (!allowedAgentIds.has(agentId)) throw new ScopeError(NOT_AVAILABLE);
  return id;
}
