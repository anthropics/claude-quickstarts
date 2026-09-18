import Anthropic from "@anthropic-ai/sdk";
import type { BetaManagedAgentsSession } from "@anthropic-ai/sdk/resources/beta/sessions/sessions";

/**
 * The shared pieces of the server side: one SDK client (auth comes from
 * ANTHROPIC_API_KEY or the credentials `ant auth login` saves), the httpOnly
 * cookie that is this app's entire notion of identity, and the ownership
 * check every route runs on that cookie. Every other API call lives in the
 * route that triggers it. There is no service layer.
 */
export const client = new Anthropic();

export const SESSION_COOKIE = "roadtrip_planner_session_id";

export function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `Missing ${name}. Run \`./agents/setup.sh\` (it writes .env), then restart \`npm run dev\`.`,
    );
  }
  return value;
}

/**
 * The gate every session-touching route goes through. The cookie value comes
 * from the browser and becomes an API path parameter, and the server's
 * Anthropic credentials can see every session in the workspace, including
 * other apps' sessions. So an ID is only trusted once it looks like an ID,
 * resolves, belongs to this quickstart's planner agent, and can still take a
 * message. Anything else is null, and the caller refuses. If you fork this,
 * keep this function in the path of anything that takes a session ID from a
 * client.
 */
export async function ownedSession(
  sessionId: string | undefined | null,
): Promise<BetaManagedAgentsSession | null> {
  const agentId = requireEnv("CLAUDE_AGENT_ID");
  if (!sessionId || !/^sesn_[A-Za-z0-9]{10,64}$/.test(sessionId)) return null;
  const session = await client.beta.sessions.retrieve(sessionId).catch(() => null);
  if (!session || session.agent.id !== agentId) return null;
  // Archived (teardown ran) or terminated sessions cannot take another message.
  if (session.archived_at || session.status === "terminated") return null;
  return session;
}
