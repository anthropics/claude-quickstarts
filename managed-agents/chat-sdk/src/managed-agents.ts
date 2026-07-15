// The chat <-> Claude Managed Agents bridge. The conversation ID *is* the
// Managed Agents session ID -- there is no mapping table and no server-side
// state. Everything here depends only on the structural BotThread interface,
// not on any particular chat surface.

import Anthropic from "@anthropic-ai/sdk";
import {
  accumulateManagedAgentsEvent,
  type AccumulatedEvent,
} from "@anthropic-ai/sdk/lib/sessions/accumulate";
import { toolLabel, toolsFence, truncate, TITLE_MAX, type BriefStats, type ToolCall } from "./brief";
import { briefCard } from "./card";

export const client = new Anthropic();

// Fresh sessions carry this title until the first message renames them; the
// retitle gate in runTurn and the sidebar fallback (src/sessions.ts) must
// agree on it.
export const DEFAULT_SESSION_TITLE = "New chat";

export function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value || value.endsWith("...")) {
    throw new Error(`${name} must be set in .env (see .env.example)`);
  }
  return value;
}

// One line of turn progress: a tool call starting or finishing, a model
// request, a thinking block, a retry. The bridge reports these through
// TurnHooks.activity; surfaces decide how to show them (the web page streams
// them to a live feed). The user-facing reply never travels here -- that is
// /api/chat's lane.
export type ActivityItem = {
  kind: "model" | "thinking" | "tool" | "tool_done" | "tool_error" | "writing" | "retry" | "waiting";
  label: string;
};

export type TurnHooks = {
  // Called for each ActivityItem as the turn produces it.
  activity?: (item: ActivityItem) => void;
  // First message of a fresh conversation: becomes the session title, so the
  // sidebar (and the Console) show what the chat is about.
  title?: string;
};

// The minimal thread surface this module needs; satisfied by the Chat SDK's
// real thread object. post() takes a complete markdown string, an async
// iterable of fragments (the Chat SDK's portable streaming API: the web
// adapter pumps each fragment onto the open response as a text-delta), or a
// card (see src/card.tsx).
export interface BotThread {
  id: string;
  post(message: string | AsyncIterable<string> | ReturnType<typeof briefCard>): Promise<unknown>;
}

const SESSION_ENDED =
  "This session has ended on the server. Start a new chat from the sidebar.";

// The event stream EOF'd mid-turn while the session keeps working server-side
// -- distinct from a failed turn, because the right advice is "check back",
// not "resend" (a resend would queue a duplicate research run).
class StreamDropped extends Error {
  constructor() {
    super("event stream ended before the turn completed");
  }
}

// Conversation IDs come from the browser, so never trust one blindly: it must
// look like an ID (it becomes an API path segment), resolve to a real
// session, belong to this quickstart's agent, and not be archived. This is
// the ownership check for every route that touches a session.
export async function ownedSession(sessionId: string) {
  if (!/^[A-Za-z0-9_-]{4,128}$/.test(sessionId)) return null;
  try {
    const session = await client.beta.sessions.retrieve(sessionId);
    if (session.agent.id !== requireEnv("CLAUDE_AGENT_ID")) return null;
    if (session.archived_at != null || session.status === "terminated") return null;
    return session;
  } catch (err) {
    // Only a definitive rejection of this ID means the session is gone: not
    // found (404/410), or 400 for an ID the API says can never resolve. A
    // transient failure (429/5xx/network) must not read as "session ended" --
    // rethrow and let the caller fail the one request instead of abandoning
    // the conversation.
    if (
      err instanceof Anthropic.APIError &&
      (err.status === 400 || err.status === 404 || err.status === 410)
    ) {
      return null;
    }
    throw err;
  }
}

// Serialize turns per thread: one stream reader per session, replies in
// order. Managed Agents queues user messages server-side; the anchor check in
// streamTurn keeps a turn from consuming its predecessor's events when an
// abandoned turn is still finishing (see the send below the stream open).
const queues = new Map<string, Promise<void>>();

export function enqueueTurn(threadId: string, turn: () => Promise<void>): Promise<void> {
  const prev = queues.get(threadId) ?? Promise.resolve();
  const next = prev.catch(() => {}).then(turn);
  queues.set(threadId, next);
  next
    .catch(() => {})
    .finally(() => {
      if (queues.get(threadId) === next) queues.delete(threadId);
    });
  return next;
}

export type EventContent = { type: string; text?: string }[] | null | undefined;

// Join an event's text blocks the same way for previews, buffered events, and
// the /api/history replay (src/sessions.ts), so all three line up character
// for character.
export function rawTextOf(content: EventContent): string {
  return (content ?? [])
    .filter((block) => block.type === "text" && block.text)
    .map((block) => block.text)
    .join("\n\n");
}

export function textOf(content: EventContent): string {
  return rawTextOf(content).trim();
}

// "web_search: solid-state batteries" reads better than "web_search". Tool
// inputs are free-form JSON; pull the first human-meaningful field and
// truncate it. Shared with the /api/history replay (src/sessions.ts) so the
// kept trace shows the same lines live and replayed.
export function toolCallOf(name: string, input: unknown): ToolCall {
  const called = truncate(name, 70);
  const args = input as Record<string, unknown> | null | undefined;
  for (const key of ["query", "url", "pattern", "path", "file_path", "command"]) {
    const value = args?.[key];
    if (typeof value === "string" && value) return { name: called, hint: truncate(value, 70) };
  }
  return { name: called, hint: "" };
}

// One streamed reply in flight. `sent` is the exact text already handed to
// thread.post; push() appends to a pending buffer an async generator drains,
// so fragments coalesce instead of queueing one array entry per token. The
// post itself starts lazily on the first non-empty fragment: a preview that
// never produces text never renders an empty bubble.
type StreamingPost = {
  sent: string;
  push(text: string): void;
  finish(): Promise<unknown>;
};

function streamingPost(thread: BotThread): StreamingPost {
  let pending = "";
  let closed = false;
  let wake = () => {};
  let posting: Promise<unknown> | undefined;
  const fragments = (async function* () {
    for (;;) {
      if (pending) {
        const chunk = pending;
        pending = "";
        yield chunk;
        continue;
      }
      if (closed) return;
      await new Promise<void>((resolve) => (wake = resolve));
    }
  })();
  const post: StreamingPost = {
    sent: "",
    push(text) {
      if (!text) return;
      post.sent += text;
      pending += text;
      if (!posting) {
        posting = thread.post(fragments);
        // Mark handled so an early failure is not an unhandled rejection;
        // finish() returns the same promise, so the failure still surfaces.
        posting.catch(() => {});
      }
      wake();
    },
    finish() {
      closed = true;
      wake();
      return posting ?? Promise.resolve();
    },
  };
  return post;
}

// One user message in, the agent's replies out. Holds an Anthropic SSE stream
// open for the whole turn (minutes for a research request) and posts each
// agent message as it lands. Never rejects: every failure path ends in a
// message to the thread.
export async function runTurn(
  thread: BotThread,
  sessionId: string,
  text: string,
  hooks: TurnHooks = {},
): Promise<void> {
  try {
    const session = await ownedSession(sessionId);
    if (!session) {
      await thread.post(SESSION_ENDED);
      return;
    }
    // Only an untitled session takes the title hint: the hint is client
    // metadata, and without this gate any request could rename an existing
    // conversation. Fire-and-forget -- a failed retitle never fails the turn.
    if (hooks.title && session.title === DEFAULT_SESSION_TITLE) {
      void client.beta.sessions
        .update(sessionId, { title: truncate(hooks.title, TITLE_MAX) })
        .catch(() => {});
    }
    const stats: BriefStats = { searches: 0, seconds: 0, sessionId };
    const tools: ToolCall[] = [];
    const startedAt = Date.now();
    const { finished, replied } = await streamTurn(thread, sessionId, text, hooks, stats, tools);
    // A cleanly ended turn closes with its trailing messages: the kept
    // tool-call trace (the live feed is progress-only and gone on reload),
    // then the brief card. Gated and ordered exactly like the /api/history
    // replay (src/sessions.ts), so live and replayed transcripts match. If
    // the held response dies before these, the turn itself is complete and
    // replay re-derives both -- their failure must never read as a failed
    // turn ("send that again" would queue a duplicate research run).
    if (finished && replied) {
      try {
        if (tools.length > 0) await thread.post(toolsFence(tools));
        if (stats.searches > 0) {
          stats.seconds = Math.round((Date.now() - startedAt) / 1000);
          await thread.post(briefCard(stats));
        }
      } catch (err) {
        console.warn(`[managed-agent] ${sessionId} trailing post failed:`, err);
      }
    }
  } catch (err) {
    console.error(`[managed-agent] turn failed for ${sessionId}:`, err);
    // A dropped stream is not a failed turn: the session finishes the
    // research server-side, so "send that again" would run it twice.
    const message =
      err instanceof StreamDropped
        ? "I lost my connection mid-research, but the work continues on the server. Reopen this chat from the sidebar in a minute or two to see the reply."
        : "Hit a snag on my end. Send that again?";
    await thread.post(message).catch(() => {});
  }
}

// A previewed agent.message being assembled: the SDK accumulator folds
// event_start / event_delta / the buffered event into one snapshot, and the
// streamed post receives whatever suffix each fold added.
type Preview = { acc: AccumulatedEvent | undefined; post: StreamingPost };

// `finished` is true when the turn ended cleanly (end_turn); false when it
// stopped early or the session died -- both already explained to the thread.
// `replied` is true once the agent posted any non-empty message text.
async function streamTurn(
  thread: BotThread,
  sessionId: string,
  text: string,
  hooks: TurnHooks,
  stats: BriefStats,
  tools: ToolCall[],
): Promise<{ finished: boolean; replied: boolean }> {
  const note = hooks.activity ?? (() => {});
  // Stream first, then send: the stream only delivers events emitted after it
  // opens, so attaching late would miss the start of the turn. `event_deltas`
  // opts this connection into token previews: `event_start` announces the id
  // a buffered `agent.message` will carry, then `event_delta` fragments
  // stream the text the model is writing right now. Previews are best-effort
  // and never persisted -- the buffered event with the same id stays
  // authoritative.
  const stream = await client.beta.sessions.events.stream(sessionId, {
    event_deltas: ["agent.message"],
  });
  // The send response names the created user.message event. A previous turn
  // can still be running server-side (Stop only abandons the response, and a
  // dropped stream leaves the research going); the message queues behind it
  // and its event reaches the stream when the session starts processing it.
  // Everything on the stream before our own event's id is therefore that
  // turn's leftovers, discarded below rather than posted as if it answered
  // this message. The event log keeps the discarded replies; reopening the
  // chat replays them.
  let anchorId: string | undefined;
  try {
    const sent = await client.beta.sessions.events.send(sessionId, {
      events: [{ type: "user.message", content: [{ type: "text", text }] }],
    });
    anchorId = sent.data?.find((event) => event.type === "user.message")?.id;
  } catch (err) {
    stream.controller.abort();
    throw err;
  }
  // No id to anchor on (unexpected response shape): process everything.
  let anchored = anchorId === undefined;

  // Previewed agent.message id -> its accumulator + streamed post.
  const previews = new Map<string, Preview>();
  // True once a persisted agent.message carried non-empty text. Preview text
  // whose buffered event never arrives (an errored model request) does not
  // count: the card mirrors what the event log can replay.
  let replied = false;
  // Tool-use event id -> its trace entry, so the matching result can report
  // by name and mark the entry failed.
  const openCalls = new Map<string, ToolCall>();
  // Fold one preview event into its snapshot and stream out the new suffix.
  // Deltas are best-effort: if they ever disagree with what we already sent,
  // stop forwarding and let the buffered event settle it.
  const advance = (preview: Preview, event: Parameters<typeof accumulateManagedAgentsEvent>[1]) => {
    try {
      preview.acc = accumulateManagedAgentsEvent(preview.acc, event);
    } catch {
      return;
    }
    const sofar = rawTextOf(preview.acc?.content as EventContent);
    if (sofar.startsWith(preview.post.sent)) preview.post.push(sofar.slice(preview.post.sent.length));
  };
  // Close every open bubble and wait for the drains, so a terminal notice or
  // the brief card really is the last thing posted. A dead response's failed
  // post must not mask the reason the bubble is closing.
  const closeOpenPreviews = async () => {
    const drains = [...previews.values()].map((preview) => preview.post.finish().catch(() => {}));
    previews.clear();
    await Promise.all(drains);
  };

  try {
    for await (const event of stream) {
      if (!anchored) {
        if (event.type === "user.message") {
          // Ours marks the start of our turn; another client's is not ours
          // to render either way.
          if (event.id === anchorId) anchored = true;
          continue;
        }
        if (event.type === "session.status_idle" && event.stop_reason?.type === "requires_action") {
          // The previous turn parked the session on an approval this bridge
          // can't answer, so the queued message will never run (see
          // skill.md's debugging table).
          await thread.post(
            "The agent asked for an approval this bridge doesn't handle, and this conversation is stuck waiting for it. Start a new chat from the sidebar; see skill.md about tool permission policies.",
          );
          return { finished: false, replied };
        }
        if (event.type !== "session.status_terminated" && event.type !== "session.deleted") {
          note({ kind: "waiting", label: "finishing the previous turn" });
          continue;
        }
        // terminated/deleted fall through: the switch below explains and exits.
      }
      switch (event.type) {
        case "event_start":
          // The model started writing a message; the bubble opens with its
          // first fragment.
          if (event.event.type === "agent.message") {
            previews.set(event.event.id, { acc: undefined, post: streamingPost(thread) });
            advance(previews.get(event.event.id) as Preview, event);
            note({ kind: "writing", label: "writing the reply" });
          }
          break;
        case "event_delta": {
          const preview = previews.get(event.event_id);
          if (preview) advance(preview, event);
          break;
        }
        case "agent.message": {
          // The buffered event is the truth. Folding it replaces the preview
          // snapshot wholesale, so the streamed bubble gets exactly the text
          // the previews had not delivered yet. If the preview somehow
          // diverged from the final text, close it and post the
          // authoritative version separately: the persisted event always
          // wins over a best-effort preview.
          const preview = previews.get(event.id);
          // Raw (untrimmed) throughout, the same shape the /api/history
          // replay posts, so live and replayed transcripts match exactly.
          const full = rawTextOf(event.content as EventContent);
          const hasText = full.trim() !== "";
          if (hasText) replied = true;
          if (preview) {
            previews.delete(event.id);
            const matched = full.startsWith(preview.post.sent);
            if (matched) advance(preview, event);
            await preview.post.finish();
            if (!matched && hasText) await thread.post(full);
          } else if (hasText) {
            await thread.post(full);
          }
          break;
        }
        case "span.model_request_start":
          note({ kind: "model", label: "model request" });
          break;
        case "span.model_request_end":
          // An errored model request never emits its buffered agent.message;
          // this event is what closes the preview it had opened.
          if (event.is_error) await closeOpenPreviews();
          break;
        case "agent.thinking":
          // Start-only: Managed Agents announces that the model is reasoning, not what.
          note({ kind: "thinking", label: "thinking" });
          break;
        case "agent.tool_use": {
          if (event.name === "web_search") stats.searches++;
          // The feed and the kept trace get the tool name plus a short
          // argument hint (the user's own query); the server log gets the
          // name only -- inputs are derived from user messages and do not
          // belong there.
          const call = toolCallOf(event.name, event.input);
          tools.push(call);
          openCalls.set(event.id, call);
          note({ kind: "tool", label: toolLabel(call) });
          console.log(`[managed-agent] ${sessionId} tool: ${event.name}`);
          break;
        }
        case "agent.tool_result": {
          const call = openCalls.get(event.tool_use_id);
          openCalls.delete(event.tool_use_id);
          if (event.is_error && call) call.error = true;
          const name = call?.name ?? "tool";
          note(
            event.is_error
              ? { kind: "tool_error", label: `${name} failed` }
              : { kind: "tool_done", label: `${name} done` },
          );
          break;
        }
        case "session.error": {
          // Operational errors (model overload, ...). The session retries on
          // its own; if retries run out, the idle stop_reason below says so.
          const error = (event as { error?: { type?: string; message?: string } }).error;
          console.warn(`[managed-agent] ${sessionId} error: ${error?.type ?? "unknown"} ${error?.message ?? ""}`);
          note({ kind: "retry", label: `${error?.type ?? "error"}, retrying` });
          break;
        }
        case "session.status_idle": {
          const stop = event.stop_reason;
          if (!stop) break;
          if (stop.type === "end_turn") return { finished: true, replied };
          await closeOpenPreviews();
          if (stop.type === "requires_action") {
            // The agent is waiting for a tool confirmation or custom tool
            // result this bridge does not implement, and it will keep waiting
            // -- retrying into the same session can never succeed. The
            // shipped agent cannot produce this; an edited one (always_ask
            // tools, custom tools) can. See skill.md's debugging table.
            await thread.post(
              "The agent asked for an approval this bridge doesn't handle, and this conversation is stuck waiting for it. Start a new chat from the sidebar; see skill.md about tool permission policies.",
            );
            return { finished: false, replied };
          }
          await thread.post(`Research run stopped early (${stop.type}). Try again.`);
          return { finished: false, replied };
        }
        case "session.status_terminated":
        case "session.deleted":
          await closeOpenPreviews();
          await thread.post(SESSION_ENDED);
          return { finished: false, replied };
      }
    }
  } finally {
    // However the loop exits, no streamed bubble is left open.
    await closeOpenPreviews();
  }

  // The stream closed without a terminal status event (clean EOF from a proxy
  // or load balancer mid-turn). Even before the anchor the message is already
  // queued server-side (the send succeeded), so runTurn's catch must NOT tell
  // the user to resend -- see StreamDropped.
  throw new StreamDropped();
}
