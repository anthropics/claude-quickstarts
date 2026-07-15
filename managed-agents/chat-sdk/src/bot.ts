// Chat SDK wiring: the web adapter turns each browser POST into a DM on a
// thread (`web:{userId}:{conversationId}`) and pumps `thread.post()` back
// onto that request's response stream, so the handler surface is one
// callback and the reply channel is the HTTP response itself. The
// conversation ID inside the thread ID is a Managed Agents session ID -- the
// page creates the session first (POST /api/sessions) and chats into it.

import { Chat } from "chat";
import { createWebAdapter } from "@chat-adapter/web";
import { createMemoryState } from "@chat-adapter/state-memory";
import { publishActivity } from "./activity";
import { enqueueTurn, runTurn } from "./managed-agents";

// The web adapter's whole security boundary: there is no platform signing a
// webhook for you, so this callback decides who the caller is for EVERY
// route that exposes a conversation (`/api/chat` via the adapter;
// `/api/activity`, `/api/sessions`, and `/api/history` via authenticate
// below). Returning null produces a 401. The demo trusts anyone who can
// reach the loopback port and gives them all the same identity, which also
// means anyone who knows a session ID can join that conversation. Swap in
// your real session lookup before exposing it; see skill.md.
function getUser(_request: Request) {
  return { id: "local", name: "you" };
}

// The same identity check, for the routes main.ts serves directly.
export { getUser as authenticate };

const adapters = {
  web: createWebAdapter({
    userName: "research-analyst",
    getUser,
    // The browser already holds the transcript and the Managed Agents session
    // holds the context; don't have the Chat SDK cache message bodies too.
    persistMessageHistory: false,
  }),
};

// The activity feed subscribes by conversation ID; the bridge publishes by
// thread ID. Resolve the caller with the same getUser the chat route uses,
// then let the adapter build the ID -- so a conversation can only be watched
// by the user it belongs to, under whatever auth getUser implements.
export async function activityThreadId(
  request: Request,
  conversationId: string,
): Promise<string | null> {
  const user = await getUser(request);
  // Mirror the adapter's own rule: a ':' in the user ID would corrupt the
  // `web:{userId}:{conversationId}` round-trip, so it never names a thread.
  if (!user || user.id.includes(":")) return null;
  return adapters.web.encodeThreadId({ userId: user.id, conversationId });
}

export const bot = new Chat<typeof adapters>({
  userName: "research-analyst",
  adapters,
  // The Chat SDK requires a state adapter for its internals (locks, message
  // dedup), but no conversation state lives here anymore -- the Managed
  // Agents session is the state. Memory state is fine even in production.
  state: createMemoryState(),
  // Don't use the SDK's per-thread lock for serialization: its TTL (30s) is
  // far shorter than a research turn. Let every message through; the
  // per-thread queue in managed-agents.ts runs the turns in order.
  concurrency: "concurrent",
});

bot.onDirectMessage(async (thread, message) => {
  const text = message.text?.trim();
  if (!text || message.author.isMe) return;
  // runTurn re-checks the ID really is one of this agent's sessions before
  // touching it.
  const { conversationId } = adapters.web.decodeThreadId(thread.id);
  // The page tags the first message of a fresh conversation with a title
  // hint; the bridge writes it onto the session so the sidebar and the
  // Console both show what the chat is about.
  const metadata = (message.raw as { metadata?: { title?: string } }).metadata;
  const title = typeof metadata?.title === "string" ? metadata.title.trim() : undefined;
  // Await the whole turn. thread.post() writes onto this request's response
  // stream, which the adapter closes as soon as the handler returns -- the
  // fire-and-forget shape that fits a Slack or WhatsApp webhook would close
  // the stream minutes before the agent answers.
  await enqueueTurn(thread.id, () =>
    runTurn(thread, conversationId, text, {
      title: title || undefined,
      activity: (item) => publishActivity(thread.id, item),
    }),
  );
});
