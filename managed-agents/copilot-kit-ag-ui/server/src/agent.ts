/**
 * An AG-UI agent backed by a Claude Managed Agents session.
 *
 * CopilotKit's runtime accepts any AG-UI `AbstractAgent`; each `run(input)`
 * becomes one turn of the managed session for that thread. The Observable is
 * the AG-UI event stream CopilotKit renders from.
 */
import Anthropic from '@anthropic-ai/sdk';
import { AbstractAgent } from '@ag-ui/client';
import { EventType, type BaseEvent, type RunAgentInput } from '@ag-ui/core';
import { Observable } from 'rxjs';
import { runBridgeTurn } from './bridge.ts';
import { forgetThread, getOrCreateThread } from './sessions.ts';

const TURN_TIMEOUT_MS = 5 * 60_000;

// Module-level singleton, NOT an instance field: CopilotKit's runtime clones
// registered agents per run, and clones don't carry instance fields.
// Zero-arg client: resolves ANTHROPIC_API_KEY or an `ant auth login` profile.
const client = new Anthropic();

const latestUserText = (input: RunAgentInput): string => {
  for (let i = input.messages.length - 1; i >= 0; i--) {
    const msg = input.messages[i]!;
    if (msg.role !== 'user') continue;
    if (typeof msg.content === 'string') return msg.content;
    return (msg.content ?? [])
      .map((part) => ('text' in part && typeof part.text === 'string' ? part.text : ''))
      .join('');
  }
  return '';
};

export class ManagedAgentFinancialAssistant extends AbstractAgent {
  /** Abort controller for the in-flight run, so abortRun() (the UI's Stop
   *  button, dispatched by the runtime) actually cancels the turn. */
  private currentRunAbort: AbortController | null = null;

  abortRun(): void {
    this.currentRunAbort?.abort();
  }

  run(input: RunAgentInput): Observable<BaseEvent> {
    return new Observable<BaseEvent>((subscriber) => {
      const disconnect = new AbortController();
      this.currentRunAbort = disconnect;
      const timeout = AbortSignal.timeout(TURN_TIMEOUT_MS);
      const signal = AbortSignal.any([disconnect.signal, timeout]);
      const emit = (event: BaseEvent) => subscriber.next(event);

      (async () => {
        console.log(`[run ${input.runId}] start (thread ${input.threadId})`);
        emit({
          type: EventType.RUN_STARTED,
          threadId: input.threadId,
          runId: input.runId,
        } as BaseEvent);

        const userText = latestUserText(input).trim();
        if (!userText) {
          emit({
            type: EventType.RUN_ERROR,
            message: 'No user message text in this run — the managed session needs a prompt.',
          } as BaseEvent);
          return;
        }

        const thread = await getOrCreateThread(client, input.threadId);
        if (thread.busy) {
          emit({
            type: EventType.RUN_ERROR,
            message: 'A run is already in progress on this thread.',
          } as BaseEvent);
          return;
        }
        thread.busy = true;

        // Once per thread: link the raw session trace in Console, where the
        // full event history (every tool call and thinking span) is visible.
        if (!thread.traceAnnounced) {
          thread.traceAnnounced = true;
          emit({
            type: EventType.ACTIVITY_SNAPSHOT,
            messageId: `trace_${thread.sessionId}`,
            activityType: 'session_trace',
            content: { url: thread.traceUrl, sessionId: thread.sessionId },
          } as BaseEvent);
        }

        let outcome;
        try {
          outcome = await runBridgeTurn({
            client,
            sessionId: thread.sessionId,
            userText,
            emit,
            signal,
          });
        } catch (err) {
          if (signal.aborted) {
            // Abandoned mid-flight (client gone or time cap) — interrupt the
            // session so it doesn't keep working into the void.
            client.beta.sessions.events
              .send(thread.sessionId, { events: [{ type: 'user.interrupt' }] })
              .catch(() => {});
          }
          if (timeout.aborted) {
            emit({
              type: EventType.RUN_ERROR,
              message: `Turn exceeded the ${TURN_TIMEOUT_MS / 1000}s time cap and was interrupted.`,
            } as BaseEvent);
            return;
          }
          throw err;
        } finally {
          thread.busy = false;
        }

        if (outcome.sessionEnded) {
          // The session is gone — drop the mapping so the next message on
          // this thread provisions a fresh one.
          forgetThread(input.threadId);
        }
        if (!outcome.errored) {
          emit({
            type: EventType.RUN_FINISHED,
            threadId: input.threadId,
            runId: input.runId,
          } as BaseEvent);
        }
      })()
        .then(() => {
          console.log(
            `[run ${input.runId}] end (disconnect=${disconnect.signal.aborted} timeout=${timeout.aborted})`,
          );
          subscriber.complete();
        })
        .catch((err) => {
          console.error('[run] failed:', err);
          if (!disconnect.signal.aborted) {
            emit({
              type: EventType.RUN_ERROR,
              message: err instanceof Error ? err.message : 'run failed',
            } as BaseEvent);
          }
          subscriber.complete();
        });

      // Teardown: CopilotKit unsubscribes when the frontend disconnects.
      return () => {
        disconnect.abort();
        if (this.currentRunAbort === disconnect) this.currentRunAbort = null;
      };
    });
  }
}
