// The one place that turns a Managed Agents event log into an assistant-ui
// conversation. It's a pure fold: the same function replays a stored session
// (GET /api/sessions/[id]/events) and folds live events off the tail, so an
// old chat and a live one can never diverge. No React, no fetching, no
// clocks: everything a test needs is an array of events.
//
// The mapping, in one table:
//   user.message                        → a user bubble
//   agent.message                       → assistant text (buffered, authoritative)
//   event_start / event_delta           → the same text, streamed early (token previews)
//   agent.thinking                      → an empty reasoning part (progress signal only)
//   agent.tool_use / mcp / custom       → a tool-call part; toolCallId is the *event* id
//   agent.tool_result / mcp / custom    → that part's result
//   user.tool_confirmation              → that part's approval, settled
//   session.status_idle{requires_action} → approval:{id} on each blocked tool part
//   session.status_running / idle       → whether the turn is live
//   session.error                       → an error message + retry chip

import type { StreamEvent, ToolUseEvent } from "./events";
import { isPersisted } from "./events";

// ---------------------------------------------------------------------------
// Message model (a structural subset of assistant-ui's ThreadMessageLike;
// the runtime casts across the boundary once, in the thread runtime hook).
// ---------------------------------------------------------------------------

/** What a tool call produced, normalized for the tool cards. */
export type ToolResultPayload = {
  text: string;
  isError: boolean;
  searchResults?: Array<{ title: string; url: string; snippet: string }>;
};

export type ToolApproval = {
  id: string;
  approved?: boolean;
  reason?: string;
};

export type TextPart = { type: "text"; text: string };
export type ReasoningPart = { type: "reasoning"; text: string };
export type ToolPart = {
  type: "tool-call";
  toolCallId: string;
  toolName: string;
  /** Managed Agents flavor of this tool, for renderers that care. */
  toolKind: "builtin" | "mcp" | "custom";
  mcpServer?: string;
  args: Record<string, unknown>;
  argsText: string;
  result?: ToolResultPayload;
  isError?: boolean;
  approval?: ToolApproval;
};
export type ContentPart = TextPart | ReasoningPart | ToolPart;

export type MessageStatus =
  | { type: "running" }
  | { type: "requires-action"; reason: "tool-calls" }
  | { type: "complete"; reason: "stop" | "unknown" }
  | { type: "incomplete"; reason: "cancelled" | "error"; error?: string };

export type ThreadMessage = {
  id: string;
  role: "assistant" | "user";
  content: ContentPart[];
  createdAt: Date;
  status?: MessageStatus;
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

/** In-flight token preview: which text part it's writing into. */
type Preview = { messageIndex: number; partIndex: number };

export type ProjectionError = {
  message: string;
  retryStatus: "retrying" | "exhausted" | "terminal";
};

export type Projection = {
  messages: readonly ThreadMessage[];
  /** The agent is actively working (session status running). */
  isRunning: boolean;
  /** The session is unrecoverable (terminated/deleted): freeze the composer. */
  isDead: boolean;
  /** Event ids of built-in/MCP tool uses waiting on a human Allow/Deny. */
  pendingApprovals: string[];
  /** Every event id the session is CURRENTLY parked on (from the latest
   *  requires_action, cleared the moment the session runs or ends). Unlike
   *  pendingApprovals it is not affected by our optimistic clicks, so it's
   *  the ground truth for "is the server still waiting on this id?". */
  parkedIds: string[];
  /** Event ids of custom tool uses the client still owes a result for. */
  pendingCustomTools: string[];
  /** Custom tool uses already answered (from history or by us). */
  answeredCustomTools: ReadonlySet<string>;
  /** Tool-use ids settled by a REAL (persisted) confirmation, as opposed
   *  to our optimistic click. A restore must never reopen these. */
  confirmedIds: ReadonlySet<string>;
  /** Optimistic user bubbles whose real echo has landed (delivered). */
  echoedOptimistic: ReadonlySet<string>;
  /** Persisted event ids already folded (dedupe across replay + tail). */
  seen: ReadonlySet<string>;
  /** Live token previews keyed by the event id they'll reconcile into. */
  previews: ReadonlyMap<string, Preview>;
  /** All tool-use events seen, keyed by event id (drives requires_action). */
  toolUses: ReadonlyMap<string, ToolUseEvent>;
  /** Most recent session.error, cleared by the next running/message. */
  lastError: ProjectionError | null;
};

export const initialProjection = (): Projection => ({
  messages: [],
  isRunning: false,
  isDead: false,
  pendingApprovals: [],
  parkedIds: [],
  pendingCustomTools: [],
  answeredCustomTools: new Set(),
  confirmedIds: new Set(),
  echoedOptimistic: new Set(),
  seen: new Set(),
  previews: new Map(),
  toolUses: new Map(),
  lastError: null,
});

// ---------------------------------------------------------------------------
// Content helpers
// ---------------------------------------------------------------------------

type LooseBlock = { type?: string; text?: string; title?: string; source?: string; content?: unknown };

function asBlocks(blocks: unknown): LooseBlock[] {
  return Array.isArray(blocks) ? (blocks as LooseBlock[]) : [];
}

function textOfBlocks(blocks: unknown): string {
  const parts: string[] = [];
  for (const block of asBlocks(blocks)) {
    if (block.type === "text" && typeof block.text === "string") parts.push(block.text);
  }
  return parts.join("\n\n");
}

/** Fold a tool_result content array into text + structured search results. */
export function toToolResult(content: unknown, isError: boolean): ToolResultPayload {
  const textParts: string[] = [];
  const searchResults: NonNullable<ToolResultPayload["searchResults"]> = [];
  for (const block of asBlocks(content)) {
    if (block.type === "text" && typeof block.text === "string") {
      textParts.push(block.text);
    } else if (block.type === "search_result") {
      searchResults.push({
        title: typeof block.title === "string" ? block.title : "",
        url: typeof block.source === "string" ? block.source : "",
        snippet: textOfBlocks(block.content).slice(0, 400),
      });
    } else if (block.type === "image") {
      textParts.push("[image]");
    } else if (block.type === "document") {
      textParts.push("[document]");
    }
  }
  return {
    text: textParts.join("\n"),
    isError,
    ...(searchResults.length ? { searchResults } : {}),
  };
}

// ---------------------------------------------------------------------------
// Immutable message helpers
// ---------------------------------------------------------------------------

const draft = (m: readonly ThreadMessage[]): ThreadMessage[] => [...m];

/** A "retrying" error is a live progress signal, not history: the moment the
 *  turn proves it recovered (produced output, or ended), the banner must go.
 *  A session that recovers in place never re-emits status_running (it was
 *  never idle), so waiting for that event would leave the banner up forever.
 *  Terminal/exhausted errors stay — they ARE the outcome. */
const clearRetrying = (err: ProjectionError | null): ProjectionError | null =>
  err?.retryStatus === "retrying" ? null : err;

// The reducer keeps no clock (a clock would make replay differ from live).
// Persisted events carry processed_at; the controller stamps its synthetic
// optimistic events too. Anything still missing a timestamp gets a fixed one.
const UNKNOWN_TIME = new Date(0);
const timeOf = (iso?: string | null) => (iso ? new Date(iso) : UNKNOWN_TIME);

// What a reasoning part says. The API exposes no thinking text, but the part
// must carry some: assistant-ui drops blank text/reasoning parts during
// conversion, and an invisible part can't signal anything.
export const THINKING_LABEL = "Thinking…";

/** Index of the assistant message that should absorb the current turn's
 *  activity, creating one if the last message is a user turn or nothing. */
function currentAssistantIndex(messages: ThreadMessage[], createdAt?: string | null): number {
  const last = messages[messages.length - 1];
  if (last && last.role === "assistant") {
    const li = messages.length - 1;
    // A message opened by a timestamp-less preview (event_start carries no
    // processed_at) gets the real time from the first persisted event that
    // lands on it, so live and replayed projections agree.
    if (createdAt && last.createdAt.getTime() === UNKNOWN_TIME.getTime()) {
      messages[li] = { ...last, createdAt: timeOf(createdAt) };
    }
    return li;
  }
  messages.push({
    id: `asst-${messages.length}`,
    role: "assistant",
    content: [],
    createdAt: timeOf(createdAt),
    status: { type: "running" },
  });
  return messages.length - 1;
}

/** A gate the server is no longer waiting on (interrupt, end of turn,
 *  termination) must not keep live Allow/Deny buttons. Strip approvals that
 *  never got an answer; leave answered ones as the record they are. */
function stripUnresolvedApprovals(messages: readonly ThreadMessage[]): readonly ThreadMessage[] {
  let changed = false;
  const next = messages.map((msg) => {
    if (msg.role !== "assistant") return msg;
    let msgChanged = false;
    const content = msg.content.map((part) => {
      if (part.type !== "tool-call" || !part.approval) return part;
      if (part.approval.approved !== undefined) return part;
      msgChanged = changed = true;
      const rest = { ...part };
      delete rest.approval;
      return rest;
    });
    return msgChanged ? { ...msg, content } : msg;
  });
  return changed ? next : messages;
}

function withContent(message: ThreadMessage, content: ContentPart[]): ThreadMessage {
  return { ...message, content };
}

/** Is `b` the echo of our optimistic bubble `a`? The client and server
 *  build the message text with the same messageText(), so a real echo is
 *  identical. A prefix match is kept as slack for a server that appends. */
function sameOpening(a: readonly ContentPart[], b: readonly ContentPart[]): boolean {
  const at = a.find((p) => p.type === "text");
  const bt = b.find((p) => p.type === "text");
  if (!at || !bt || at.type !== "text" || bt.type !== "text") return false;
  if (!at.text || !bt.text) return at.text === bt.text;
  return at.text === bt.text || bt.text.startsWith(at.text) || at.text.startsWith(bt.text);
}

/** Find a tool-call part by its toolCallId (= the tool-use event id). */
function findToolPart(messages: readonly ThreadMessage[], toolCallId: string) {
  for (let mi = messages.length - 1; mi >= 0; mi--) {
    const msg = messages[mi]!;
    if (msg.role !== "assistant") continue;
    const pi = msg.content.findIndex((p) => p.type === "tool-call" && p.toolCallId === toolCallId);
    if (pi !== -1) return { mi, pi } as const;
  }
  return null;
}

/** Replace one part inside one message, immutably. */
function updatePart(
  messages: ThreadMessage[],
  mi: number,
  pi: number,
  update: (part: ContentPart) => ContentPart,
) {
  const msg = messages[mi];
  if (!msg || pi < 0 || pi >= msg.content.length) return;
  const content = [...msg.content];
  content[pi] = update(content[pi]!);
  messages[mi] = withContent(msg, content);
}

function dropEmptyPreviews(
  messages: readonly ThreadMessage[],
  previews: ReadonlyMap<string, Preview>,
): readonly ThreadMessage[] {
  if (previews.size === 0) return messages;
  const emptyByMsg = new Map<number, Set<number>>();
  for (const [, p] of previews) {
    const part = messages[p.messageIndex]?.content[p.partIndex];
    if (part?.type === "text" && part.text === "") {
      let indices = emptyByMsg.get(p.messageIndex);
      if (!indices) {
        indices = new Set();
        emptyByMsg.set(p.messageIndex, indices);
      }
      indices.add(p.partIndex);
    }
  }
  if (emptyByMsg.size === 0) return messages;
  const next = draft(messages);
  for (const [mi, indices] of emptyByMsg) {
    const msg = next[mi];
    if (!msg) continue;
    next[mi] = withContent(
      msg,
      msg.content.filter((_, pi) => !indices.has(pi)),
    );
  }
  return next;
}

const updateTool =
  (patch: Partial<ToolPart> | ((p: ToolPart) => Partial<ToolPart>)) =>
  (part: ContentPart): ContentPart => {
    if (part.type !== "tool-call") return part;
    const change = typeof patch === "function" ? patch(part) : patch;
    return { ...part, ...change };
  };

// ---------------------------------------------------------------------------
// Status
// ---------------------------------------------------------------------------

/** The last assistant message carries the turn's live status; earlier ones
 *  are settled history. Explicit status wins over assistant-ui's auto-status,
 *  which is what lets the approval buttons appear while the composer stays
 *  in "the agent is busy" mode. */
function withDerivedStatuses(state: Projection): Projection {
  let li = -1;
  for (let i = state.messages.length - 1; i >= 0; i--) {
    if (state.messages[i]!.role === "assistant") {
      li = i;
      break;
    }
  }
  if (li === -1) return state;
  const last = state.messages[li]!;

  // The live status belongs to the current turn's assistant message only.
  // When a newer user bubble follows it, a new turn has begun and this
  // message is settled history: it must never read as running again,
  // whatever the session is doing now (the new turn's own assistant message
  // will carry the live status once it exists).
  const isCurrentTurn = li === state.messages.length - 1;

  let status: MessageStatus;
  if (!isCurrentTurn) {
    status = { type: "complete", reason: "unknown" };
  } else if (state.pendingApprovals.length > 0 || state.pendingCustomTools.length > 0) {
    status = { type: "requires-action", reason: "tool-calls" };
  } else if (state.isRunning) {
    status = { type: "running" };
  } else if (state.lastError && state.lastError.retryStatus !== "retrying") {
    status = { type: "incomplete", reason: "error", error: state.lastError.message };
  } else {
    status = { type: "complete", reason: "unknown" };
  }

  if (JSON.stringify(last.status ?? null) === JSON.stringify(status)) return state;
  const messages = draft(state.messages);
  messages[li] = { ...last, status };
  return { ...state, messages };
}

// ---------------------------------------------------------------------------
// The fold
// ---------------------------------------------------------------------------

export function applyEvent(state: Projection, event: StreamEvent): Projection {
  // Replay and tail overlap by design (the stream opens before history is
  // fetched, so no gap can appear); dedupe on the persisted event id.
  // Previews carry no id and are handled by their event_id instead.
  if (isPersisted(event)) {
    if (state.seen.has(event.id)) return state;
    state = { ...state, seen: new Set(state.seen).add(event.id) };
  }
  return withDerivedStatuses(applyEventInner(state, event));
}

function applyEventInner(state: Projection, event: StreamEvent): Projection {
  switch (event.type) {
    // ---------------------------------------------------------------- turns
    case "user.message": {
      const messages = draft(state.messages);
      const bubble: ThreadMessage = {
        id: event.id,
        role: "user",
        content: [{ type: "text", text: textOfBlocks(event.content) }],
        createdAt: timeOf(event.processed_at),
      };
      // The controller shows a sent message immediately as an "optimistic-"
      // bubble; the real echoed event replaces its content but KEEPS the id.
      // assistant-ui keys messages by id: a new id at the same slot reads as
      // a second branch of an edited message (a phantom "2 / 2" picker).
      const last = messages[messages.length - 1];
      let echoedOptimistic = state.echoedOptimistic;
      // Reconcile against the trailing optimistic bubble only when this is its
      // echo: it sits at the end and opens with the same text (the server and
      // client build the text with the same messageText(), so a genuine echo
      // matches exactly). No clock comparison, since client and server
      // clocks disagree; the controller guarantees stored history is fully
      // folded before any optimistic bubble exists, so a historic message
      // can't land here after the bubble.
      const isEcho =
        !!last &&
        last.role === "user" &&
        last.id.startsWith("optimistic-") &&
        sameOpening(last.content, bubble.content);
      if (isEcho) {
        messages[messages.length - 1] = { ...bubble, id: last.id };
        // The echo landed: this bubble is delivered, so a late send-failure
        // rollback must never evict it.
        echoedOptimistic = new Set(state.echoedOptimistic).add(last.id);
      } else {
        messages.push(bubble);
      }
      // A fresh user turn makes any previous error history.
      return { ...state, messages, echoedOptimistic, lastError: null };
    }

    case "session.status_running":
      // The session left the gate (or a new turn began): nothing is parked,
      // so no Allow/Deny can still be live. This also sweeps a gate a failed
      // /confirm may have reopened after the server had in fact resumed.
      // Safe with several gates parked at once: answering only a subset
      // re-emits status_idle{requires_action} with the remainder (which
      // re-stamps those gates) rather than status_running; running fires
      // only after every parked id is answered.
      return {
        ...state,
        messages: stripUnresolvedApprovals(state.messages),
        isRunning: true,
        parkedIds: [],
        pendingApprovals: [],
        lastError: null,
      };

    case "session.status_rescheduled":
      // Transient error; the session retries on its own. Keep showing "busy".
      return { ...state, isRunning: true };

    case "session.status_idle": {
      const stop = event.stop_reason;
      if (stop.type !== "requires_action") {
        // The turn ended (or gave up) with no gate outstanding: any Allow/Deny
        // still on screen was abandoned (interrupted while parked).
        return {
          ...state,
          messages: dropEmptyPreviews(stripUnresolvedApprovals(state.messages), state.previews),
          isRunning: false,
          pendingApprovals: [],
          parkedIds: [],
          pendingCustomTools: [],
          previews: new Map(),
          lastError: clearRetrying(state.lastError),
        };
      }
      // The turn is parked on human input. Each blocked event id is either a
      // tool the user must Allow/Deny, or a custom tool we must answer.
      const messages = draft(state.messages);
      const pendingApprovals: string[] = [];
      const pendingCustomTools: string[] = [];
      const parkedIds = [...stop.event_ids];
      for (const id of stop.event_ids) {
        const toolUse = state.toolUses.get(id);
        if (!toolUse) continue;
        if (toolUse.type === "agent.custom_tool_use") {
          if (!state.answeredCustomTools.has(id)) pendingCustomTools.push(id);
          continue;
        }
        pendingApprovals.push(id);
        // Stamp the gate onto the tool part: assistant-ui renders Allow/Deny
        // from `approval.id` (leave an already-answered approval alone).
        const found = findToolPart(messages, id);
        if (found) {
          updatePart(messages, found.mi, found.pi, updateTool((p) =>
            p.approval && p.approval.approved !== undefined ? {} : { approval: { id } },
          ));
        }
      }
      return {
        ...state,
        messages,
        isRunning: false,
        pendingApprovals,
        parkedIds,
        pendingCustomTools,
        // Parking on a gate proves a mid-turn "retrying" recovered too.
        lastError: clearRetrying(state.lastError),
      };
    }

    case "session.status_terminated":
    case "session.deleted":
      return {
        ...state,
        messages: dropEmptyPreviews(stripUnresolvedApprovals(state.messages), state.previews),
        isRunning: false,
        isDead: true,
        pendingApprovals: [],
        parkedIds: [],
        pendingCustomTools: [],
        previews: new Map(),
      };

    // ------------------------------------------------------------- thinking
    // agent.thinking carries no reasoning text in the current API: it is a
    // "started working" signal. The part needs SOME text — assistant-ui's
    // fromThreadMessageLike drops text/reasoning parts whose text is blank —
    // so it carries a fixed placeholder label rather than invented content.
    case "event_start": {
      // A preview for an event whose PERSISTED form already folded (replay
      // finished after the event completed) must not open a second part —
      // the persisted copy dedupes on `seen`, so nothing would ever
      // reconcile the duplicate away.
      if (state.seen.has(event.event.id)) return state;
      if (event.event.type !== "agent.thinking" && event.event.type !== "agent.message") {
        return state;
      }
      const messages = draft(state.messages);
      const mi = currentAssistantIndex(messages);
      const msg = messages[mi]!;
      if (event.event.type === "agent.thinking") {
        // Register the part as a preview: the buffered agent.thinking arrives
        // with the same id and reconciles into it (no second part, and it
        // backfills the timestamp this start event doesn't carry).
        const content: ContentPart[] = [...msg.content, { type: "reasoning", text: THINKING_LABEL }];
        messages[mi] = withContent(msg, content);
        const previews = new Map(state.previews).set(event.event.id, {
          messageIndex: mi,
          partIndex: content.length - 1,
        });
        return { ...state, messages, previews };
      }
      // agent.message preview: open an empty text part the deltas fill.
      const content: ContentPart[] = [...msg.content, { type: "text", text: "" }];
      messages[mi] = withContent(msg, content);
      const previews = new Map(state.previews).set(event.event.id, {
        messageIndex: mi,
        partIndex: content.length - 1,
      });
      return { ...state, messages, previews };
    }

    case "agent.thinking": {
      // Previewed by event_start: the part exists; just settle the preview
      // and backfill the real timestamp the start event couldn't know.
      const preview = state.previews.get(event.id);
      if (preview) {
        const previews = new Map(state.previews);
        previews.delete(event.id);
        const messages = draft(state.messages);
        const msg = messages[preview.messageIndex];
        if (msg && msg.createdAt.getTime() === UNKNOWN_TIME.getTime()) {
          messages[preview.messageIndex] = { ...msg, createdAt: timeOf(event.processed_at) };
        }
        return { ...state, messages, previews };
      }
      const messages = draft(state.messages);
      const mi = currentAssistantIndex(messages, event.processed_at);
      const msg = messages[mi]!;
      messages[mi] = withContent(msg, [...msg.content, { type: "reasoning", text: THINKING_LABEL }]);
      return { ...state, messages };
    }

    // -------------------------------------------------------- token stream
    case "event_delta": {
      const preview = state.previews.get(event.event_id);
      if (!preview) return state; // a delta whose start we never saw
      const delta = event.delta;
      if (delta.type !== "content_delta" || delta.content.type !== "text") return state;
      const messages = draft(state.messages);
      updatePart(messages, preview.messageIndex, preview.partIndex, (part) =>
        part.type === "text" ? { ...part, text: part.text + delta.content.text } : part,
      );
      return { ...state, messages };
    }

    case "agent.message": {
      // The buffered message is authoritative. If a preview streamed a prefix
      // of it, reconcile in place (a preview is always a verbatim prefix);
      // otherwise append it whole (no streaming gate, or a missed start).
      const messages = draft(state.messages);
      const text = textOfBlocks(event.content);
      const preview = state.previews.get(event.id);
      const previews = new Map(state.previews);
      if (preview) {
        previews.delete(event.id);
        updatePart(messages, preview.messageIndex, preview.partIndex, (part) =>
          part.type === "text" ? { ...part, text } : part,
        );
        // The preview opened the message without a timestamp; the buffered
        // event has the real one, and replay will use it too.
        const msg = messages[preview.messageIndex];
        if (msg && msg.createdAt.getTime() === UNKNOWN_TIME.getTime()) {
          messages[preview.messageIndex] = { ...msg, createdAt: timeOf(event.processed_at) };
        }
        // Output proves a mid-turn "retrying" recovered (no status_running
        // re-fires for an in-place recovery).
        return { ...state, messages, previews, lastError: clearRetrying(state.lastError) };
      }
      const mi = currentAssistantIndex(messages, event.processed_at);
      const msg = messages[mi]!;
      messages[mi] = withContent(msg, [...msg.content, { type: "text", text }]);
      return { ...state, messages, previews, lastError: clearRetrying(state.lastError) };
    }

    case "span.model_request_end": {
      // An errored model request never emits its buffered agent.message.
      // Close any preview it left open so it doesn't hang half-written.
      if (!event.is_error || state.previews.size === 0) return state;
      const messages = draft(state.messages);
      for (const [, preview] of state.previews) {
        updatePart(messages, preview.messageIndex, preview.partIndex, (part) =>
          part.type === "text" ? { ...part, text: `${part.text} …` } : part,
        );
      }
      return { ...state, messages, previews: new Map() };
    }

    // ------------------------------------------------------------- tools
    case "agent.tool_use":
    case "agent.mcp_tool_use":
    case "agent.custom_tool_use": {
      const messages = draft(state.messages);
      const mi = currentAssistantIndex(messages, event.processed_at);
      const msg = messages[mi]!;
      const args = (event.input && typeof event.input === "object" ? event.input : {}) as Record<
        string,
        unknown
      >;
      const part: ToolPart = {
        type: "tool-call",
        toolCallId: event.id,
        toolName: event.name,
        toolKind:
          event.type === "agent.tool_use" ? "builtin" : event.type === "agent.mcp_tool_use" ? "mcp" : "custom",
        ...(event.type === "agent.mcp_tool_use" ? { mcpServer: event.mcp_server_name } : {}),
        args,
        argsText: JSON.stringify(args, null, 2),
      };
      messages[mi] = withContent(msg, [...msg.content, part]);
      const toolUses = new Map(state.toolUses).set(event.id, event);
      return { ...state, messages, toolUses };
    }

    case "agent.tool_result":
    case "agent.mcp_tool_result": {
      const toolCallId = event.type === "agent.tool_result" ? event.tool_use_id : event.mcp_tool_use_id;
      const found = findToolPart(state.messages, toolCallId);
      if (!found) return state;
      const messages = draft(state.messages);
      const result = toToolResult(event.content, !!event.is_error);
      updatePart(messages, found.mi, found.pi, updateTool((p) => ({
        result,
        isError: result.isError,
        // A result arriving proves the gate was allowed, even if the echoed
        // confirmation raced past us. Leave an answered approval alone.
        approval: p.approval && p.approval.approved === undefined ? { ...p.approval, approved: true } : p.approval,
      })));
      return { ...state, messages };
    }

    case "user.custom_tool_result": {
      // Our own answer to a custom tool, echoed back (or replayed). Mark it
      // done so a reattach never answers the same call twice.
      const id = event.custom_tool_use_id;
      const answeredCustomTools = new Set(state.answeredCustomTools).add(id);
      let messages: readonly ThreadMessage[] = state.messages;
      const found = findToolPart(messages, id);
      if (found) {
        const next = draft(messages);
        const result = toToolResult(event.content, !!event.is_error);
        updatePart(next, found.mi, found.pi, updateTool({ result, isError: result.isError }));
        messages = next;
      }
      return {
        ...state,
        messages,
        answeredCustomTools,
        pendingCustomTools: state.pendingCustomTools.filter((x) => x !== id),
      };
    }

    case "user.tool_confirmation": {
      // Our Allow/Deny, echoed (live) or replayed (history). Settle the gate.
      const id = event.tool_use_id;
      // A persisted (non-optimistic) confirmation is the server's own
      // record of the answer: from here on it can never be reopened.
      const confirmedIds = event.id.startsWith("optimistic-confirm-")
        ? state.confirmedIds
        : new Set(state.confirmedIds).add(id);
      let messages: readonly ThreadMessage[] = state.messages;
      const found = findToolPart(messages, id);
      if (found) {
        const next = draft(messages);
        updatePart(next, found.mi, found.pi, updateTool({
          approval: {
            id,
            approved: event.result === "allow",
            ...(event.deny_message ? { reason: event.deny_message } : {}),
          },
        }));
        messages = next;
      }
      return {
        ...state,
        messages,
        confirmedIds,
        pendingApprovals: state.pendingApprovals.filter((x) => x !== id),
      };
    }

    // ------------------------------------------------------------- errors
    case "session.error": {
      const err = event.error as { message?: string; retry_status?: { type?: string } };
      const retryStatus = (err.retry_status?.type ?? "terminal") as ProjectionError["retryStatus"];
      const lastError = { message: err.message ?? "The session hit an error.", retryStatus };
      // A terminal error can land before the agent said anything this turn.
      // Make sure there's an assistant message for the error to sit on.
      if (retryStatus === "retrying") return { ...state, lastError };
      const messages = draft(state.messages);
      currentAssistantIndex(messages, event.processed_at);
      return { ...state, messages, lastError };
    }

    default:
      // Span, thread (multi-agent), outcome, compaction and update events
      // are progress signals this UI doesn't render. Ignore, don't fail.
      return state;
  }
}

/** Fold a whole ordered event list. */
export function project(events: Iterable<StreamEvent>, from = initialProjection()): Projection {
  let state = from;
  for (const event of events) state = applyEvent(state, event);
  return state;
}

/** The turn is not something the user can type over: agent working, or a
 *  gate waiting for a click, or a custom tool we still owe. */
export const isBusy = (state: Projection): boolean =>
  state.isRunning || state.pendingApprovals.length > 0 || state.pendingCustomTools.length > 0;

/** The user just answered the last open gate: the session is about to
 *  resume server-side. Mark it running now so the composer doesn't briefly
 *  reopen (and accept a message mid-resume) before the real status_running
 *  arrives. Deliberately NOT a folded status_running event: that would clear
 *  parkedIds, which restoreGates needs intact if the confirmation POST
 *  fails. */
export function markResuming(state: Projection): Projection {
  if (isBusy(state)) return state; // gates still open, or already running
  return withDerivedStatuses({ ...state, isRunning: true });
}

// ---------------------------------------------------------------------------
// Recovery operations (used by the controller when an optimistic action
// fails). These are not events: they undo local optimism so the UI converges
// on what the server actually did, which a dedupe-by-id replay cannot.
// ---------------------------------------------------------------------------

/** A confirmation POST failed. Put back only the gates the server is still
 *  actually parked on: `parkedIds` is untouched by our optimistic click, so
 *  it tells us whether the session left the gate meanwhile (an interrupt,
 *  or an answer that landed via the tail even though our fetch errored). A
 *  part that already has a verdict or a result is left alone. If nothing
 *  qualifies, this is a no-op and the settled state stands. */
export function restoreGates(state: Projection, ids: readonly string[]): Projection {
  const restorable = ids.filter((id) => state.parkedIds.includes(id));
  if (restorable.length === 0) return state;
  const messages = draft(state.messages);
  const pendingApprovals = [...state.pendingApprovals];
  let changed = false;
  for (const id of restorable) {
    // A REAL confirmation already settled this on the server (its echo folded
    // before our fetch errored): the answer landed, so don't reopen it.
    if (state.confirmedIds.has(id)) continue;
    const found = findToolPart(messages, id);
    if (!found) continue;
    const part = messages[found.mi]!.content[found.pi]!;
    // Likewise if the tool already ran (result present).
    if (part.type !== "tool-call" || part.result !== undefined) continue;
    updatePart(messages, found.mi, found.pi, updateTool({ approval: { id } }));
    if (!pendingApprovals.includes(id)) pendingApprovals.push(id);
    changed = true;
  }
  if (!changed) return state;
  // Gates restored means the server is still parked: undo any optimistic
  // "resuming" flag markResuming set when the click looked final.
  return withDerivedStatuses({ ...state, messages, pendingApprovals, isRunning: false });
}

/** A message POST failed. If the bubble was never echoed, it wasn't sent and
 *  must not sit in the transcript reading as delivered: evict it (and the
 *  optimistic "running" it started). If the echo already landed, the message
 *  WAS delivered (the failure was only on our side of the response), so
 *  keep it. */
export function evictOptimisticMessage(state: Projection, optimisticId: string): Projection {
  if (state.echoedOptimistic.has(optimisticId)) return state;
  const idx = state.messages.findIndex((m) => m.id === optimisticId);
  if (idx === -1) return { ...state, isRunning: false };
  const messages = draft(state.messages);
  messages.splice(idx, 1);
  let previews = state.previews;
  if (previews.size > 0) {
    const shifted = new Map<string, Preview>();
    for (const [id, p] of previews) {
      if (p.messageIndex < idx) shifted.set(id, p);
      else if (p.messageIndex > idx) shifted.set(id, { ...p, messageIndex: p.messageIndex - 1 });
    }
    previews = shifted;
  }
  return withDerivedStatuses({ ...state, messages, previews, isRunning: false });
}
