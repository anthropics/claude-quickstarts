import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import Anthropic from "@anthropic-ai/sdk";
import { z, type ZodRawShape } from "zod";
import * as managedAgents from "./managed-agents";
import {
  AGENT_ID,
  assertAgentAllowed,
  EVENT_ID,
  resolveAllowedSession,
  ScopeError,
  SESSION_ID,
} from "./scope";

// Agent output comes back to the calling model inside these results. It stays
// a JSON text block, which is data. Tool descriptions below are fixed strings
// and never include anything an agent produced.
function json(result: unknown) {
  return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
}

function failure(message: string) {
  return { content: [{ type: "text" as const, text: message }], isError: true };
}

// An SDK error object can carry the request's headers. Only its status and
// type go back to the caller, and nothing else is logged.
function describe(err: unknown): string {
  if (err instanceof ScopeError) return err.message;
  if (err instanceof Anthropic.APIError) {
    const type = (err.error as { error?: { type?: string } } | undefined)?.error?.type;
    return `Anthropic API error ${err.status ?? ""}${type ? ` (${type})` : ""}`.trim();
  }
  return "The request failed.";
}

const agentId = z.string().regex(AGENT_ID, "must look like agent_...");
const sessionId = z.string().regex(SESSION_ID, "must look like sesn_...");
const eventId = z.string().regex(EVENT_ID, "must look like sevt_...");

/**
 * What a tool touches. It is a required argument, and the wrapper below runs
 * the matching check from scope.ts BEFORE the handler, so a new tool cannot
 * reach the API without one:
 *   "agent":   has an agent_id   → assertAgentAllowed
 *   "session": has a session_id  → resolveAllowedSession (retrieves the session
 *              and checks its agent before any send, interrupt, archive, or stream)
 *   "listing": takes no ID       → the handler must filter to the allowlist itself
 */
type Scope = "agent" | "session" | "listing";

/** Register all nine tools on an MCP server. Shared by the stdio and HTTP entrypoints. */
export function registerTools(server: McpServer) {
  function tool<S extends ZodRawShape>(
    name: string,
    scope: Scope,
    description: string,
    shape: S,
    handler: (args: z.objectOutputType<S, z.ZodTypeAny>) => Promise<unknown>,
  ) {
    // Catch a mislabelled tool when the server starts, not when it is called.
    if (scope === "agent" && !("agent_id" in shape)) throw new Error(`${name}: scope "agent" needs an agent_id`);
    if (scope === "session" && !("session_id" in shape)) throw new Error(`${name}: scope "session" needs a session_id`);
    if (scope === "listing" && ("agent_id" in shape || "session_id" in shape)) {
      throw new Error(`${name}: a tool that takes an ID cannot have scope "listing"`);
    }

    server.tool(name, description, shape, (async (args: z.objectOutputType<S, z.ZodTypeAny>) => {
      try {
        const ids = args as { agent_id?: string; session_id?: string };
        if (scope === "agent") assertAgentAllowed(ids.agent_id ?? "");
        if (scope === "session") await resolveAllowedSession(managedAgents.client, ids.session_id ?? "");
        return json(await handler(args));
      } catch (err) {
        const message = describe(err);
        // stderr in both transports (stdout is the protocol on stdio). The tool
        // name and the short message only: never the arguments or the error object.
        console.error(`[managed-agents-mcp] ${name} failed: ${message}`);
        return failure(message);
      }
    }) as never);
  }

  // --- Tier 1: 1:1 session primitives -------------------------------------

  tool(
    "list_agents",
    "listing",
    "List the Managed Agents this server can reach. Use name_contains to filter in busy workspaces.",
    {
      limit: z.number().int().min(1).max(200).optional().describe("Default 50"),
      name_contains: z.string().max(200).optional().describe("Case-insensitive substring match on agent name"),
    },
    ({ limit, name_contains }) => managedAgents.listAgents({ limit, name_contains }),
  );

  tool(
    "get_agent",
    "agent",
    "Get the full configuration of one Managed Agent.",
    { agent_id: agentId },
    ({ agent_id }) => managedAgents.getAgent(agent_id),
  );

  tool(
    "create_session",
    "agent",
    "Start a new session with a Managed Agent. Returns a session_id. Pass it to send_message and wait_for_idle on every later turn.",
    {
      agent_id: agentId.describe("Agent ID from list_agents"),
      title: z.string().max(200).optional(),
    },
    ({ agent_id, title }) => managedAgents.createSession(agent_id, title),
  );

  tool(
    "send_message",
    "session",
    "Send a user message to a running session. Returns immediately. Call wait_for_idle to get the reply.",
    {
      session_id: sessionId,
      text: z.string().min(1).max(100_000).describe("The user's message, verbatim"),
    },
    ({ session_id, text }) => managedAgents.sendMessage(session_id, text),
  );

  tool(
    "interrupt",
    "session",
    "Interrupt a running session. The agent stops at the next safe point and goes idle.",
    { session_id: sessionId },
    ({ session_id }) => managedAgents.interrupt(session_id),
  );

  tool(
    "get_session",
    "session",
    "Get a session's current status, usage, and metadata.",
    { session_id: sessionId },
    ({ session_id }) => managedAgents.getSession(session_id),
  );

  tool(
    "list_events",
    "session",
    "List a session's event log (messages, tool calls, status changes), oldest first. Returns up to limit events. When has_more is true, call again with after_id set to last_event_id.",
    {
      session_id: sessionId,
      after_id: eventId.optional().describe("Only return events after this event ID"),
      limit: z.number().int().min(1).max(500).optional().describe("Default 100"),
    },
    ({ session_id, after_id, limit }) => managedAgents.listEvents(session_id, after_id, limit),
  );

  tool(
    "archive_session",
    "session",
    "Archive a session when the conversation is finished. Frees resources, and the session becomes read-only.",
    { session_id: sessionId },
    ({ session_id }) => managedAgents.archiveSession(session_id),
  );

  // --- Tier 1.5: the SSE to request/response shim --------------------------

  tool(
    "wait_for_idle",
    "session",
    'Block until the agent finishes the current turn and return its reply text. Call this right after send_message. status "idle" means the turn finished. "timeout" means it is still running, so call again. "requires_action", "retries_exhausted", "budget_reached", and "terminated" mean the turn stopped without finishing, and reply may be partial.',
    {
      session_id: sessionId,
      timeout_sec: z.number().int().min(5).max(600).optional().describe("Default 120"),
    },
    ({ session_id, timeout_sec }) => managedAgents.waitForIdle(session_id, timeout_sec),
  );
}
