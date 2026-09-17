import type {
  BetaManagedAgentsAgentMessageEvent,
  BetaManagedAgentsSessionEvent,
} from "@anthropic-ai/sdk/resources/beta/sessions/events";

/** A persisted session event, straight from the SDK. */
export type ManagedAgentEvent = BetaManagedAgentsSessionEvent;

/**
 * The render model, built by folding the session's event log. This one fold
 * is the whole "state management" of the app: it runs over `events.list` on
 * load and over the same array as the live tail appends to it, so history
 * and streaming render identically by construction.
 */

export type ToolCall = {
  id: string;
  name: string;
  input: unknown;
  state: "running" | "ok" | "error";
  output: string;
};

export type TurnStats = {
  modelRequests: number;
  toolCalls: number;
  inputTokens: number;
  outputTokens: number;
};

/**
 * One side of an agent-to-agent exchange. `sent` is the planner handing its
 * draft to a roster agent (`agent.thread_message_sent`); `received` is the
 * reply landing back (`agent.thread_message_received`). `agentName` is the
 * roster agent on the far side, from the event's `to_agent_name` /
 * `from_agent_name`.
 */
export type ThreadMessage = {
  id: string;
  direction: "sent" | "received";
  agentName: string;
  text: string;
};

export type TurnPart =
  | { kind: "text"; id: string; text: string; streaming: boolean }
  | { kind: "tool"; call: ToolCall }
  | { kind: "thread_message"; message: ThreadMessage };

export type ModelUsage = {
  inputTokens: number;
  outputTokens: number;
  cacheReadTokens: number;
  cacheCreateTokens: number;
};

/**
 * One entry in the rail's event timeline. `live` means the event is still in
 * flight on the stream right now: a tool call awaiting its result, a model
 * request span that has not ended, a thinking block whose `event_start`
 * arrived but whose buffered event has not, or a subagent thread that is
 * still running. `agent.message` is not a rail item: it streams in the chat
 * itself.
 */
export type RailItem =
  | { kind: "tool"; id: string; live: boolean; call: ToolCall }
  | { kind: "model"; id: string; live: boolean; error: boolean; usage: ModelUsage | null }
  | { kind: "thinking"; id: string; live: boolean }
  | { kind: "thread"; id: string; live: boolean; agentName: string; threadId: string }
  | { kind: "thread_message"; id: string; live: boolean; message: ThreadMessage };

export type Turn = {
  /** the `user.message` event id that opened the turn */
  id: string;
  userText: string;
  parts: TurnPart[];
  /** every event of the turn in stream order, for the rail */
  rail: RailItem[];
  stats: TurnStats;
};

/**
 * Fold the event log into turns. `preview` is the live `agent.message`
 * snapshot the accumulator is growing right now: it renders as a streaming
 * text part until the buffered event with the same id lands in the log and
 * replaces it (same id, so the part does not jump). `liveThinkingId` is a
 * thinking block whose `event_start` arrived but whose buffered event has
 * not. Thinking previews are start-only, so an id is all the stream gives.
 */
export function foldTranscript(
  events: ManagedAgentEvent[],
  preview?: BetaManagedAgentsAgentMessageEvent | null,
  liveThinkingId?: string | null,
): Turn[] {
  const turns: Turn[] = [];
  let turn: Turn | null = null;
  const calls = new Map<string, ToolCall>();
  const toolItems = new Map<string, Extract<RailItem, { kind: "tool" }>>();
  const modelItems = new Map<string, Extract<RailItem, { kind: "model" }>>();
  // keyed by sthr_ id: the status events that settle a thread carry the
  // thread id, not the thread_created event id
  const threadItems = new Map<string, Extract<RailItem, { kind: "thread" }>>();

  for (const event of events) {
    if (event.type === "user.message") {
      turn = {
        id: event.id,
        userText: textOfBlocks(event.content),
        parts: [],
        rail: [],
        stats: { modelRequests: 0, toolCalls: 0, inputTokens: 0, outputTokens: 0 },
      };
      turns.push(turn);
      continue;
    }
    if (!turn) continue; // nothing renders before the first user message

    switch (event.type) {
      case "agent.message":
        turn.parts.push({
          kind: "text",
          id: event.id,
          text: textOfBlocks(event.content),
          streaming: false,
        });
        break;
      case "agent.thinking":
        turn.rail.push({ kind: "thinking", id: event.id, live: false });
        break;
      case "agent.tool_use": {
        const call: ToolCall = {
          id: event.id,
          name: event.name,
          input: event.input,
          state: "running",
          output: "",
        };
        calls.set(event.id, call);
        turn.stats.toolCalls += 1;
        turn.parts.push({ kind: "tool", call });
        const item: Extract<RailItem, { kind: "tool" }> = {
          kind: "tool",
          id: event.id,
          live: true,
          call,
        };
        toolItems.set(event.id, item);
        turn.rail.push(item);
        break;
      }
      case "agent.tool_result": {
        const call = calls.get(event.tool_use_id);
        if (!call) break; // result for a call outside this log slice
        call.state = event.is_error === true ? "error" : "ok";
        call.output = clampToolOutput(textOfBlocks(event.content));
        const item = toolItems.get(event.tool_use_id);
        if (item) item.live = false;
        break;
      }
      case "span.model_request_start": {
        const item: Extract<RailItem, { kind: "model" }> = {
          kind: "model",
          id: event.id,
          live: true,
          error: false,
          usage: null,
        };
        modelItems.set(event.id, item);
        turn.rail.push(item);
        break;
      }
      case "span.model_request_end": {
        turn.stats.modelRequests += 1;
        turn.stats.inputTokens += event.model_usage.input_tokens;
        turn.stats.outputTokens += event.model_usage.output_tokens;
        const item = modelItems.get(event.model_request_start_id);
        if (item) {
          item.live = false;
          item.error = event.is_error === true;
          item.usage = {
            inputTokens: event.model_usage.input_tokens,
            outputTokens: event.model_usage.output_tokens,
            cacheReadTokens: event.model_usage.cache_read_input_tokens,
            cacheCreateTokens: event.model_usage.cache_creation_input_tokens,
          };
        }
        break;
      }
      case "session.thread_created": {
        const item: Extract<RailItem, { kind: "thread" }> = {
          kind: "thread",
          id: event.id,
          live: true,
          agentName: event.agent_name,
          threadId: event.session_thread_id,
        };
        threadItems.set(event.session_thread_id, item);
        turn.rail.push(item);
        break;
      }
      case "session.thread_status_running": {
        const item = threadItems.get(event.session_thread_id);
        if (item) item.live = true;
        break;
      }
      case "session.thread_status_idle":
      case "session.thread_status_terminated": {
        const item = threadItems.get(event.session_thread_id);
        if (item) item.live = false;
        break;
      }
      // The agents talking to each other. Both directions land in the rail
      // (full text) and in the chat as a chip, so the handoff is visible
      // without opening the rail.
      case "agent.thread_message_sent": {
        const message: ThreadMessage = {
          id: event.id,
          direction: "sent",
          agentName: event.to_agent_name ?? "primary",
          text: textOfBlocks(event.content),
        };
        turn.parts.push({ kind: "thread_message", message });
        turn.rail.push({ kind: "thread_message", id: event.id, live: false, message });
        break;
      }
      case "agent.thread_message_received": {
        const message: ThreadMessage = {
          id: event.id,
          direction: "received",
          agentName: event.from_agent_name ?? "primary",
          text: textOfBlocks(event.content),
        };
        turn.parts.push({ kind: "thread_message", message });
        turn.rail.push({ kind: "thread_message", id: event.id, live: false, message });
        break;
      }
      case "session.status_idle":
        // An interrupted turn never gets results for its in-flight calls,
        // so the idle that ends the turn settles them.
        for (const call of calls.values()) {
          if (call.state === "running") {
            call.state = "error";
            call.output = "interrupted";
          }
        }
        for (const item of toolItems.values()) item.live = false;
        for (const item of modelItems.values()) item.live = false;
        for (const item of threadItems.values()) item.live = false;
        break;
      default:
        break;
    }
  }

  // The live previews render at the end of the last turn, unless their
  // buffered events already landed (then the log copies above are the truth).
  if (turns.length > 0) {
    const last = turns[turns.length - 1];
    if (preview && !last.parts.some((part) => part.kind === "text" && part.id === preview.id)) {
      last.parts.push({
        kind: "text",
        id: preview.id,
        text: textOfBlocks(preview.content),
        streaming: true,
      });
    }
    if (liveThinkingId && !last.rail.some((item) => item.id === liveThinkingId)) {
      last.rail.push({ kind: "thinking", id: liveThinkingId, live: true });
    }
  }

  return turns;
}

/** Flatten the text blocks of a Managed Agents content array. */
function textOfBlocks(content: Array<{ type: string; text?: string }> | undefined): string {
  return (content ?? [])
    .filter((block) => block.type === "text" && typeof block.text === "string")
    .map((block) => block.text)
    .join("\n");
}

/**
 * Tool results are curl output, routinely tens of KB of JSON. The chat only
 * needs enough to show the call worked. The full payload stays in the
 * session's event log (`events.list`, or the Console). Nothing is lost, it
 * is just not re-rendered.
 */
function clampToolOutput(text: string): string {
  const limit = 4_000;
  if (text.length <= limit) return text;
  return `${text.slice(0, limit)}\n... [${text.length - limit} more characters in the event log]`;
}
