import Anthropic from "@anthropic-ai/sdk";
import { allowedAgentIds, parseEventId } from "./scope";

// The functions below take IDs that tools.ts has already run through
// scope.ts. Call them from anywhere else and you skip the allowlist.
export const client = new Anthropic();

if (!process.env.CLAUDE_ENVIRONMENT_ID) {
  throw new Error("CLAUDE_ENVIRONMENT_ID is required (see README.md, step 1)");
}
const ENVIRONMENT_ID: string = process.env.CLAUDE_ENVIRONMENT_ID;

// Agent output goes back to the calling model inside a tool result. Cap each
// field so one huge tool input cannot blow the caller's context.
const MAX_FIELD_CHARS = 4000;

type AgentSummary = { id: string; name: string; description: string | null; model: string };

function summarizeAgent(a: Anthropic.Beta.BetaManagedAgentsAgent): AgentSummary {
  return {
    id: a.id,
    name: a.name,
    description: a.description ?? null,
    model: typeof a.model === "string" ? a.model : a.model.id,
  };
}

// --- Tier 1: 1:1 endpoint wrappers ----------------------------------------

export async function listAgents(opts: { limit?: number; name_contains?: string } = {}) {
  const limit = opts.limit ?? 50;
  const needle = opts.name_contains?.toLowerCase();
  const out: AgentSummary[] = [];
  const keep = (a: Anthropic.Beta.BetaManagedAgentsAgent) => {
    if (needle && !a.name.toLowerCase().includes(needle)) return;
    out.push(summarizeAgent(a));
  };

  if (allowedAgentIds) {
    // Fetch exactly the allowed agents. Listing the workspace and filtering
    // would work too, but this never touches an agent outside the list.
    for (const id of allowedAgentIds) {
      if (out.length >= limit) break;
      try {
        keep(await client.beta.agents.retrieve(id));
      } catch (err) {
        if (!(err instanceof Anthropic.NotFoundError)) throw err;
      }
    }
    return out;
  }

  for await (const a of client.beta.agents.list()) {
    keep(a);
    if (out.length >= limit) break;
  }
  return out;
}

export async function getAgent(agent_id: string) {
  return await client.beta.agents.retrieve(agent_id);
}

export async function createSession(agent_id: string, title?: string) {
  const session = await client.beta.sessions.create({
    agent: agent_id,
    environment_id: ENVIRONMENT_ID,
    ...(title ? { title } : {}),
  });
  return { session_id: session.id, status: session.status };
}

export async function sendMessage(session_id: string, text: string) {
  await client.beta.sessions.events.send(session_id, {
    events: [{ type: "user.message", content: [{ type: "text", text }] }],
  });
  return { queued: true };
}

export async function interrupt(session_id: string) {
  await client.beta.sessions.events.send(session_id, {
    events: [{ type: "user.interrupt" }],
  });
  return { queued: true };
}

export async function getSession(session_id: string) {
  const s = await client.beta.sessions.retrieve(session_id);
  return {
    id: s.id,
    status: s.status,
    title: s.title,
    agent: s.agent,
    created_at: s.created_at,
    updated_at: s.updated_at,
    usage: s.usage,
  };
}

export async function listEvents(session_id: string, after_id?: string, limit = 100) {
  const after = after_id ? parseEventId(after_id) : undefined;
  // A long session has thousands of events. Return a page, and tell the caller
  // there is more, so one call cannot flood its context.
  const max = Math.min(500, Math.max(1, Math.floor(limit)));
  const events: ReturnType<typeof summarizeEvent>[] = [];
  let skip = Boolean(after);
  let has_more = false;
  for await (const e of client.beta.sessions.events.list(session_id)) {
    if (skip) {
      if (e.id === after) skip = false;
      continue;
    }
    if (events.length >= max) {
      has_more = true;
      break;
    }
    events.push(summarizeEvent(e));
  }
  return { events, has_more, last_event_id: events.at(-1)?.id };
}

export async function archiveSession(session_id: string) {
  await client.beta.sessions.archive(session_id);
  return { archived: true };
}

// --- Tier 1.5: the one convenience verb -----------------------------------

type WaitStatus =
  | "idle"
  | "requires_action"
  | "retries_exhausted"
  | "budget_reached"
  | "terminated"
  | "timeout";

/**
 * Stream session events until the agent goes idle (or terminates, or the
 * deadline passes). Collects agent.message text into `reply`. This is the
 * SSE to request/response shim MCP needs, and the only place this server
 * editorializes over the raw API.
 *
 * `status` is "idle" only when the agent finished its turn (end_turn). The
 * other stop reasons come back under their own name, so a turn that is parked
 * on an approval or ran out of budget does not look like a finished reply.
 */
export async function waitForIdle(session_id: string, timeout_sec = 120) {
  const seconds = Math.min(600, Math.max(5, Math.floor(timeout_sec)));

  const replies: string[] = [];
  const activity: string[] = [];
  let status: WaitStatus = "timeout";
  let last_event_id: string | undefined;

  // The deadline aborts the connection. Checking the clock only when an event
  // arrives would hang forever on a session that emits nothing.
  const abort = new AbortController();
  const timer = setTimeout(() => abort.abort(), seconds * 1000);
  try {
    const stream = await client.beta.sessions.events.stream(session_id, {}, { signal: abort.signal });
    for await (const e of stream) {
      // Preview events (event_start, event_delta) carry no id. This stream does
      // not ask for them, but the type allows them.
      if ("id" in e && typeof e.id === "string") last_event_id = e.id;
      if (e.type === "agent.message") {
        let text = "";
        for (const b of e.content ?? []) {
          if (b.type === "text") text += b.text;
        }
        if (text) replies.push(text);
      } else if (e.type === "agent.tool_use" || e.type === "agent.mcp_tool_use") {
        activity.push(`→ ${clip(e.name, 200)}`);
      } else if (e.type === "session.status_idle") {
        const reason = e.stop_reason?.type;
        status = !reason || reason === "end_turn" ? "idle" : reason;
        break;
      } else if (e.type === "session.status_terminated") {
        status = "terminated";
        break;
      }
    }
  } catch (err) {
    if (!abort.signal.aborted) throw err;
    status = "timeout";
  } finally {
    clearTimeout(timer);
    // Drop the SSE connection so it doesn't linger after an early break.
    abort.abort();
  }

  // The stream only carries events that happen after it attaches. If the turn
  // finished in the gap between send_message and this call, the idle event was
  // never seen and the loop above ran out the clock. The log has the answer.
  if (status === "timeout" && replies.length === 0) {
    const finished = await lastTurnFromLog(session_id);
    if (finished) return finished;
  }

  return {
    status,
    reply: replies.join("\n\n").trim(),
    tool_activity: activity,
    last_event_id,
  };
}

/** The most recent turn, read from the event log, if the session has stopped. */
async function lastTurnFromLog(session_id: string) {
  const session = await client.beta.sessions.retrieve(session_id);
  if (session.status !== "idle" && session.status !== "terminated") return null;

  let replies: string[] = [];
  let activity: string[] = [];
  let status: WaitStatus | null = session.status === "terminated" ? "terminated" : null;
  let last_event_id: string | undefined;
  for await (const e of client.beta.sessions.events.list(session_id)) {
    last_event_id = e.id;
    if (e.type === "user.message") {
      // A new turn starts here. Keep only what follows the last one.
      replies = [];
      activity = [];
      if (status !== "terminated") status = null;
    } else if (e.type === "agent.message") {
      let text = "";
      for (const b of e.content ?? []) {
        if (b.type === "text") text += b.text;
      }
      if (text) replies.push(text);
    } else if (e.type === "agent.tool_use" || e.type === "agent.mcp_tool_use") {
      activity.push(`→ ${clip(e.name, 200)}`);
    } else if (e.type === "session.status_idle" && status !== "terminated") {
      const reason = e.stop_reason?.type;
      status = !reason || reason === "end_turn" ? "idle" : reason;
    }
  }
  // Idle with no idle event after the last user.message means that message has
  // not started running yet. That is still a timeout, not a finished turn.
  if (!status) return null;
  return { status, reply: replies.join("\n\n").trim(), tool_activity: activity, last_event_id };
}

// --- helpers --------------------------------------------------------------

function clip(value: unknown, max = MAX_FIELD_CHARS): string {
  const s = typeof value === "string" ? value : JSON.stringify(value) ?? "";
  return s.length > max ? `${s.slice(0, max)}… [${s.length - max} more characters]` : s;
}

function summarizeEvent(e: Anthropic.Beta.Sessions.BetaManagedAgentsSessionEvent) {
  const base = { id: e.id, type: e.type, processed_at: e.processed_at };
  if (e.type === "agent.message") {
    let text = "";
    for (const b of e.content ?? []) {
      if (b.type === "text") text += b.text;
    }
    return { ...base, text: clip(text) };
  }
  if (e.type === "agent.tool_use" || e.type === "agent.mcp_tool_use") {
    return { ...base, name: clip(e.name, 200), input: clip(e.input) };
  }
  if (e.type === "agent.tool_result" || e.type === "agent.mcp_tool_result") {
    return { ...base, is_error: e.is_error };
  }
  if (e.type === "session.status_idle") {
    return { ...base, stop_reason: e.stop_reason };
  }
  return base;
}
