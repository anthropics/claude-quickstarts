/**
 * Translate one Managed Agents session turn into AG-UI events.
 *
 * Anthropic side (SSE from /v1/sessions/{id}/events/stream):
 *   event_start / event_delta   — live previews of agent.message text, opted
 *                                 into via `event_deltas` (new in SDK 0.109)
 *   agent.message               — the buffered, canonical message
 *   agent.tool_use/tool_result  — built-in toolset calls (web_search, bash, …)
 *   session.status_idle         — turn boundary (gate on stop_reason!)
 *
 * AG-UI side (consumed by CopilotKit):
 *   TEXT_MESSAGE_START/CONTENT/END — streaming assistant text
 *   TOOL_CALL_* / TOOL_CALL_RESULT — the agent's tool activity
 */
import type Anthropic from '@anthropic-ai/sdk';
import {
  accumulateManagedAgentsEvent,
  type AccumulatedEvent,
} from '@anthropic-ai/sdk/lib/sessions/accumulate';
import type { BetaManagedAgentsStreamSessionEvents } from '@anthropic-ai/sdk/resources/beta/sessions/events';
import { EventType, type BaseEvent } from '@ag-ui/core';
import { isVizTool } from './vizTools.ts';

export interface BridgeOptions {
  client: Anthropic;
  sessionId: string;
  /** Text of the user turn to send to the session. */
  userText: string;
  /** Emit one AG-UI event toward the CopilotKit frontend. */
  emit: (event: BaseEvent) => void;
  /** Abort signal: client disconnect or the turn's wall-clock timeout. */
  signal: AbortSignal;
}

export interface BridgeOutcome {
  /** True when the bridge already emitted RUN_ERROR — skip RUN_FINISHED. */
  errored: boolean;
  /** True when the session itself is gone (terminated/deleted): the caller
   *  should forget the thread mapping so the next message starts fresh. */
  sessionEnded?: boolean;
}

const textOf = (content: ReadonlyArray<{ type: string }> | undefined): string =>
  (content ?? [])
    .filter((b): b is { type: 'text'; text: string } => b.type === 'text' && 'text' in b)
    .map((b) => b.text)
    .join('');

/** Search-result text arrives HTML-entity-encoded; decode the common ones.
 *  This is untrusted web content: an out-of-range numeric entity would make
 *  fromCodePoint throw and kill the turn, so map those to U+FFFD instead. */
const codePointOf = (n: number): string =>
  Number.isInteger(n) && n >= 0 && n <= 0x10ffff ? String.fromCodePoint(n) : '\ufffd';

const decodeEntities = (s: string): string =>
  s
    .replace(/&#x([0-9a-fA-F]+);/g, (_, hex) => codePointOf(parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_, dec) => codePointOf(Number(dec)))
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&');

/** Tool results mix block types: text, search results, images, documents. */
const describeToolResult = (content: ReadonlyArray<Record<string, unknown>> | undefined): string =>
  (content ?? [])
    .map((block) => {
      if (block.type === 'text' && typeof block.text === 'string') {
        return decodeEntities(block.text);
      }
      if (block.type === 'search_result') {
        const inner = Array.isArray(block.content) ? textOf(block.content) : '';
        return `[search result] ${decodeEntities(String(block.title ?? ''))} — ${String(
          block.source ?? '',
        )}${inner ? `\n${decodeEntities(inner).slice(0, 300)}` : ''}`;
      }
      return `[${String(block.type)}]`;
    })
    .join('\n')
    .trim();

/** Run one turn against the managed session, translating events as they arrive. */
export async function runBridgeTurn(opts: BridgeOptions): Promise<BridgeOutcome> {
  const { client, sessionId, emit, signal } = opts;

  // Stream-first: open the SSE stream (with live previews) BEFORE sending the
  // user message, so no early events are missed.
  const stream = await client.beta.sessions.events.stream(
    sessionId,
    { event_deltas: ['agent.message', 'agent.thinking'] },
    { signal },
  );

  try {
    await client.beta.sessions.events.send(sessionId, {
      events: [{ type: 'user.message', content: [{ type: 'text', text: opts.userText }] }],
    });
  } catch (err) {
    // Don't leak the already-open upstream stream when the send fails.
    stream.controller.abort();
    throw err;
  }

  // Per-previewed-message snapshots, folded with the SDK's new
  // `accumulateManagedAgentsEvent` helper. The snapshot tracks exactly what
  // the best-effort previews delivered, so the buffered canonical
  // `agent.message` can top up anything the deltas dropped.
  const previews = new Map<string, AccumulatedEvent>();
  // Messages force-closed by a terminal span end (error/interrupt mid-turn) —
  // ignore their buffered event if it straggles in afterwards.
  const closed = new Set<string>();
  // Custom tool calls we've already answered, so the requires_action idle that
  // follows them is expected rather than a hang.
  const ackedToolUses = new Set<string>();
  // Thinking spans still shown as active — resolved by the buffered
  // agent.thinking, or force-resolved when the turn ends abnormally.
  const openThinking = new Set<string>();

  const closeMessage = (messageId: string) => {
    emit({ type: EventType.TEXT_MESSAGE_END, messageId } as BaseEvent);
    previews.delete(messageId);
    closed.add(messageId);
  };

  // Every exit from the loop must leave no message open: RUN_FINISHED (or
  // RUN_ERROR-then-complete) with an active TEXT_MESSAGE is a protocol
  // violation the AG-UI verify stage rejects. Also settle any thinking rows
  // still marked active so the UI doesn't pulse forever after an error.
  const closeAllMessages = () => {
    for (const messageId of [...previews.keys()]) closeMessage(messageId);
    for (const thinkingId of [...openThinking]) {
      emit({
        type: EventType.ACTIVITY_SNAPSHOT,
        messageId: thinkingId,
        activityType: 'thinking',
        content: { state: 'done' },
      } as BaseEvent);
    }
    openThinking.clear();
  };

  const consume = async (): Promise<BridgeOutcome> => {
  for await (const event of stream as AsyncIterable<BetaManagedAgentsStreamSessionEvents>) {
    switch (event.type) {
      // ---- live previews (event delta streaming) --------------------------
      case 'event_start': {
        if (event.event.type === 'agent.message') {
          emit({
            type: EventType.TEXT_MESSAGE_START,
            messageId: event.event.id,
            role: 'assistant',
          } as BaseEvent);
          previews.set(event.event.id, accumulateManagedAgentsEvent(undefined, event)!);
        } else if (event.event.type === 'agent.thinking') {
          // agent.thinking is a progress signal without the reasoning text in
          // the current API — surface it as an activity row the UI renders.
          openThinking.add(event.event.id);
          emit({
            type: EventType.ACTIVITY_SNAPSHOT,
            messageId: event.event.id,
            activityType: 'thinking',
            content: { state: 'thinking' },
          } as BaseEvent);
        }
        break;
      }

      // Buffered confirmation that a thinking stretch finished. Snapshots with
      // an existing messageId update in place, so this flips the same row.
      case 'agent.thinking': {
        openThinking.delete(event.id);
        emit({
          type: EventType.ACTIVITY_SNAPSHOT,
          messageId: event.id,
          activityType: 'thinking',
          content: { state: 'done' },
        } as BaseEvent);
        break;
      }

      case 'event_delta': {
        const snapshot = previews.get(event.event_id);
        if (!snapshot) break; // preview we never saw the start of — ignore
        previews.set(event.event_id, accumulateManagedAgentsEvent(snapshot, event) ?? snapshot);
        if (event.delta.type === 'content_delta') {
          emit({
            type: EventType.TEXT_MESSAGE_CONTENT,
            messageId: event.event_id,
            delta: event.delta.content.text,
          } as BaseEvent);
        }
        break;
      }

      // ---- buffered canonical events --------------------------------------
      case 'agent.message': {
        if (closed.has(event.id)) break; // already force-closed on span end
        const snapshot = previews.get(event.id);
        const finalText = textOf(event.content);
        if (!snapshot) {
          // No preview seen (deltas shed) — emit the whole message at once.
          emit({
            type: EventType.TEXT_MESSAGE_START,
            messageId: event.id,
            role: 'assistant',
          } as BaseEvent);
          if (finalText) {
            emit({
              type: EventType.TEXT_MESSAGE_CONTENT,
              messageId: event.id,
              delta: finalText,
            } as BaseEvent);
          }
        } else {
          // Deltas are best-effort; the buffered event is canonical. Top up
          // whatever the previews didn't deliver.
          const previewed = textOf(snapshot.content);
          if (finalText.startsWith(previewed)) {
            if (finalText.length > previewed.length) {
              emit({
                type: EventType.TEXT_MESSAGE_CONTENT,
                messageId: event.id,
                delta: finalText.slice(previewed.length),
              } as BaseEvent);
            }
          } else {
            // The preview diverged from the canonical text. Close the
            // corrupted bubble and re-emit the authoritative message whole.
            closeMessage(event.id);
            if (finalText) {
              const messageId = `corrected_${event.id}`;
              emit({ type: EventType.TEXT_MESSAGE_START, messageId, role: 'assistant' } as BaseEvent);
              emit({ type: EventType.TEXT_MESSAGE_CONTENT, messageId, delta: finalText } as BaseEvent);
              emit({ type: EventType.TEXT_MESSAGE_END, messageId } as BaseEvent);
            }
            break;
          }
        }
        closeMessage(event.id);
        break;
      }

      // ---- generative UI: custom tools rendered by the browser ------------
      case 'agent.custom_tool_use': {
        emit({ type: EventType.TOOL_CALL_START, toolCallId: event.id, toolCallName: event.name } as BaseEvent);
        emit({ type: EventType.TOOL_CALL_ARGS, toolCallId: event.id, delta: JSON.stringify(event.input) } as BaseEvent);
        emit({ type: EventType.TOOL_CALL_END, toolCallId: event.id } as BaseEvent);

        // These tools ARE their rendering: CopilotKit draws the interactive
        // component from the args, so the session just needs an ack to keep
        // the turn moving.
        const resultText =
          isVizTool(event.name) ?
            `Rendered "${event.name}" to the user as an interactive visual.`
          : `Unknown client tool "${event.name}" — nothing was rendered.`;
        emit({
          type: EventType.TOOL_CALL_RESULT,
          messageId: `result_${event.id}`,
          toolCallId: event.id,
          content: resultText,
          role: 'tool',
        } as BaseEvent);
        try {
          await client.beta.sessions.events.send(sessionId, {
            events: [
              {
                type: 'user.custom_tool_result',
                custom_tool_use_id: event.id,
                content: [{ type: 'text', text: resultText }],
                is_error: !isVizTool(event.name),
              },
            ],
          });
        } catch (err) {
          // A failed ack would leave the session blocked in requires_action —
          // interrupt it so it isn't stranded, then let the run error out.
          client.beta.sessions.events
            .send(sessionId, { events: [{ type: 'user.interrupt' }] })
            .catch(() => {});
          throw err;
        }
        ackedToolUses.add(event.id);
        break;
      }

      // ---- built-in tool activity (web_search, bash, read, …) -------------
      case 'agent.tool_use': {
        emit({ type: EventType.TOOL_CALL_START, toolCallId: event.id, toolCallName: event.name } as BaseEvent);
        emit({ type: EventType.TOOL_CALL_ARGS, toolCallId: event.id, delta: JSON.stringify(event.input) } as BaseEvent);
        emit({ type: EventType.TOOL_CALL_END, toolCallId: event.id } as BaseEvent);
        break;
      }
      case 'agent.tool_result': {
        emit({
          type: EventType.TOOL_CALL_RESULT,
          messageId: `result_${event.tool_use_id}`,
          toolCallId: event.tool_use_id,
          content: describeToolResult(
            event.content as ReadonlyArray<Record<string, unknown>> | undefined,
          ).slice(0, 2000),
          role: 'tool',
        } as BaseEvent);
        break;
      }

      // ---- spans ------------------------------------------------------------
      case 'span.model_request_end': {
        // If the request ended without its buffered event (error/interrupt),
        // the preview never reconciles — close anything still open. On normal
        // turns the buffered agent.message always precedes this event.
        closeAllMessages();
        break;
      }

      // ---- turn boundaries --------------------------------------------------
      case 'session.error': {
        const message =
          'error' in event && event.error && typeof event.error === 'object' && 'message' in event.error ?
            String((event.error as { message?: unknown }).message)
          : 'session error';
        closeAllMessages();
        emit({ type: EventType.RUN_ERROR, message } as BaseEvent);
        return { errored: true };
      }

      case 'session.status_idle': {
        if (event.stop_reason.type === 'requires_action') {
          // Expected when it refers to viz tool calls we've already acked —
          // the session resumes on its own. Anything else would hang until
          // the time cap, so interrupt and fail loudly instead.
          const blockedOn = event.stop_reason.event_ids;
          if (blockedOn.length > 0 && blockedOn.every((id) => ackedToolUses.has(id))) break;
          await client.beta.sessions.events
            .send(sessionId, { events: [{ type: 'user.interrupt' }] })
            .catch(() => {});
          closeAllMessages();
          emit({
            type: EventType.RUN_ERROR,
            message: 'The agent requested a client-side action this demo does not support.',
          } as BaseEvent);
          return { errored: true };
        }
        closeAllMessages();
        return { errored: false }; // end_turn or retries_exhausted
      }

      case 'session.status_terminated':
      case 'session.deleted':
        // Termination can mean an error or external cleanup; either way this
        // thread's session cannot take another turn.
        closeAllMessages();
        emit({
          type: EventType.RUN_ERROR,
          message: 'This session ended on the server. Send another message to start a fresh one.',
        } as BaseEvent);
        return { errored: true, sessionEnded: true };

      default:
        break; // user echoes, thinking signals, status_running, etc.
    }
  }

  closeAllMessages();

  // The SDK stream treats an abort as a clean end of stream rather than an
  // error, so the Stop button and the turn time cap both land HERE, not in a
  // catch. Rethrow so the caller can interrupt the session and report the
  // right outcome (see agent.ts).
  if (signal.aborted) throw new Error('turn aborted');

  // Clean EOF without a terminal status event: the server closed the stream
  // mid-turn. Say so rather than passing a truncated turn off as finished.
  emit({
    type: EventType.RUN_ERROR,
    message: 'The session event stream ended before the reply completed.',
  } as BaseEvent);
  return { errored: true };
  };

  try {
    return await consume();
  } finally {
    // However the turn exits — return, throw, or abort-EOF — no TEXT_MESSAGE
    // may stay open when the outcome is reported (a protocol violation the
    // AG-UI verify stage rejects). Idempotent with the in-loop closes.
    closeAllMessages();
  }
}
