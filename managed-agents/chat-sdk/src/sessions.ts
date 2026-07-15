// The sidebar's data source. There is no database: Managed Agents sessions
// ARE the conversation store. Listing, creating, and replaying a chat are all
// plain API calls against /v1/sessions -- restart the server and every
// conversation is still here.

import { cardFence, toolsFence, type ToolCall } from "./brief";
import {
  client,
  DEFAULT_SESSION_TITLE,
  ownedSession,
  rawTextOf,
  requireEnv,
  textOf,
  toolCallOf,
  type EventContent,
} from "./managed-agents";

export type SessionSummary = {
  id: string;
  title: string;
  status: string;
  created_at: string;
};

type SessionLike = { id: string; title?: string | null; status: string; created_at: string };

function toSummary(session: SessionLike): SessionSummary {
  return {
    id: session.id,
    title: session.title || DEFAULT_SESSION_TITLE,
    status: session.status,
    created_at: session.created_at,
  };
}

// Sessions for this quickstart's agent only -- agent_id is a server-side
// filter, and archived sessions are excluded by default.
export async function listSessions(): Promise<SessionSummary[]> {
  const sessions: SessionSummary[] = [];
  for await (const session of client.beta.sessions.list({
    agent_id: requireEnv("CLAUDE_AGENT_ID"),
    limit: 50,
  })) {
    // Terminated sessions can't be replayed or resumed (ownedSession rejects
    // them), so a sidebar entry would just be a dead button.
    if (session.status === "terminated") continue;
    sessions.push(toSummary(session));
    if (sessions.length >= 50) break;
  }
  return sessions.sort((a, b) => b.created_at.localeCompare(a.created_at));
}

// "New chat" in the sidebar. The session is created before the first message
// is sent, so its ID can be the useChat conversation ID from the start; the
// first message retitles it (see runTurn).
export async function createSession(): Promise<SessionSummary> {
  const session = await client.beta.sessions.create({
    agent: requireEnv("CLAUDE_AGENT_ID"),
    environment_id: requireEnv("CLAUDE_ENVIRONMENT_ID"),
    title: DEFAULT_SESSION_TITLE,
    metadata: { quickstart: "chat-sdk" },
  });
  console.log(`[managed-agent] new session ${session.id}`);
  return toSummary(session);
}

// What useChat expects as initial messages: id + role + text parts.
type UIMessageJSON = {
  id: string;
  role: "user" | "assistant";
  parts: { type: "text"; text: string }[];
};

// Rebuild a conversation's transcript from the session's event log -- the
// single source of truth. user.message and agent.message events become chat
// bubbles; each research turn's tool-call trace and "brief ready" card are
// re-derived from the same log (tool events + processed_at timestamps), so
// both survive a server restart without being stored anywhere. The trace is
// re-derived only for turns that ended cleanly -- `session.status_idle`
// with `end_turn` persists in the log -- matching what the live path
// posted: a stopped-early turn gets neither on replay either.
// Callers must have passed the session through ownedSession() first, and
// pass its status along: a session still running its turn hasn't finished
// the research, so the final turn doesn't get its trace or card yet.
export async function historyOf(sessionId: string, status?: string): Promise<UIMessageJSON[]> {
  const messages: UIMessageJSON[] = [];
  let searches = 0;
  let tools: ToolCall[] = [];
  const openCalls = new Map<string, ToolCall>();
  let endedClean = false;
  let turnStartedAt: string | null = null;
  let lastReplyAt: string | null = null;
  let lastReplyId = "";

  const closeTurn = () => {
    // Only a cleanly ended turn gets its trailing messages -- the same
    // `finished` gate the live bridge applies (src/managed-agents.ts) --
    // and in the same order: trace, then card.
    if (!endedClean || !lastReplyId) return;
    if (tools.length > 0) {
      messages.push({
        id: `${lastReplyId}-tools`,
        role: "assistant",
        parts: [{ type: "text", text: toolsFence(tools) }],
      });
    }
    if (searches === 0) return;
    const seconds =
      turnStartedAt && lastReplyAt
        ? Math.max(0, Math.round((Date.parse(lastReplyAt) - Date.parse(turnStartedAt)) / 1000))
        : 0;
    messages.push({
      id: `${lastReplyId}-card`,
      role: "assistant",
      parts: [{ type: "text", text: cardFence({ searches, seconds, sessionId }) }],
    });
  };

  for await (const event of client.beta.sessions.events.list(sessionId)) {
    switch (event.type) {
      case "user.message": {
        closeTurn();
        searches = 0;
        tools = [];
        openCalls.clear();
        endedClean = false;
        turnStartedAt = event.processed_at ?? null;
        lastReplyId = "";
        const text = textOf(event.content as EventContent);
        if (text) messages.push({ id: event.id, role: "user", parts: [{ type: "text", text }] });
        break;
      }
      case "agent.message": {
        // Raw (untrimmed), matching what the live bridge streams -- see
        // rawTextOf in src/managed-agents.ts.
        const text = rawTextOf(event.content as EventContent);
        if (text.trim()) {
          messages.push({ id: event.id, role: "assistant", parts: [{ type: "text", text }] });
          lastReplyAt = event.processed_at ?? null;
          lastReplyId = event.id;
        }
        break;
      }
      case "agent.tool_use": {
        if (event.name === "web_search") searches++;
        const call = toolCallOf(event.name, event.input);
        tools.push(call);
        openCalls.set(event.id, call);
        break;
      }
      case "agent.tool_result": {
        const call = openCalls.get(event.tool_use_id);
        openCalls.delete(event.tool_use_id);
        if (event.is_error && call) call.error = true;
        break;
      }
      case "session.status_idle":
        if (event.stop_reason?.type === "end_turn") endedClean = true;
        break;
    }
  }
  // Earlier turns are closed by the next user.message; the final turn only
  // gets its trace and card once the session is done with it (the endedClean
  // flag makes the status check belt-and-braces).
  if (status !== "running") closeTurn();
  return messages;
}

export { ownedSession };
