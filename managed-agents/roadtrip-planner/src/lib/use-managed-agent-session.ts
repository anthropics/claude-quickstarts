"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  accumulateManagedAgentsEvent,
  type AccumulatedEvent,
} from "@anthropic-ai/sdk/lib/sessions/accumulate";
import type { BetaManagedAgentsStreamSessionEvents } from "@anthropic-ai/sdk/resources/beta/sessions/events";
import { foldTranscript, type ManagedAgentEvent, type Turn } from "./transcript";

/**
 * The client runtime, in three pieces:
 *
 *   1. One EventSource on `/api/stream`, the session's SSE tail. Every
 *      (re)connect re-fetches the event log first: the stream is a tail,
 *      not a replay, and previews are never persisted.
 *   2. The SDK's `accumulateManagedAgentsEvent` folds preview deltas into a
 *      growing snapshot, and the buffered `agent.message` with the same id
 *      retires it.
 *   3. `foldTranscript` renders the event array as turns, the same fold for
 *      first paint and live streaming.
 *
 * Send is one `user.message` (`/api/chat`) and the reply arrives on the
 * stream. Stop is a real `user.interrupt` (`/api/interrupt`).
 */

export type Activity = {
  kind: "thinking" | "retrying" | "delegating";
  message?: string;
};

/** Append log events the array does not have yet. The log's order wins. */
function mergeLog(authoritative: ManagedAgentEvent[], current: ManagedAgentEvent[]) {
  const ids = new Set(authoritative.map((event) => event.id));
  return [...authoritative, ...current.filter((event) => !ids.has(event.id))];
}

export function useManagedAgentSession(boot: {
  sessionId: string;
  events: ManagedAgentEvent[];
  working: boolean;
}) {
  const [events, setEvents] = useState<ManagedAgentEvent[]>(boot.events);
  const [preview, setPreview] = useState<AccumulatedEvent | null>(null);
  // Thinking previews are start-only (no deltas, no content), so the live
  // state is just "this thinking event id is open right now".
  const [liveThinkingId, setLiveThinkingId] = useState<string | null>(null);
  const [working, setWorking] = useState(boot.working);
  const [activity, setActivity] = useState<Activity | null>(null);
  const [error, setError] = useState<string | null>(null);

  const apply = useCallback((event: BetaManagedAgentsStreamSessionEvents) => {
    switch (event.type) {
      // ---- the preview lane: present because the stream opts into event_deltas ----
      case "event_start":
        if (event.event.type === "agent.thinking") {
          setActivity({ kind: "thinking" });
          setLiveThinkingId(event.event.id);
          return; // the accumulator only tracks agent.message previews
        }
        setPreview((open) => accumulateManagedAgentsEvent(open ?? undefined, event) ?? null);
        return;
      case "event_delta":
        // A delta for a preview that never opened here (attached
        // mid-generation) is dropped. The buffered event delivers it whole.
        setPreview((open) =>
          !open || event.event_id !== open.id
            ? open
            : (accumulateManagedAgentsEvent(open, event) ?? open),
        );
        return;
      default:
        break;
    }

    // ---- buffered events: persisted, authoritative, appended to the log ----
    if ("processed_at" in event && event.processed_at) {
      setEvents((current) => (current.some((e) => e.id === event.id) ? current : [...current, event]));
    }
    switch (event.type) {
      case "agent.message":
        // The buffered copy just landed in the log, so retire its preview.
        setPreview((open) => (open?.id === event.id ? null : open));
        return;
      case "agent.thinking":
        setActivity({ kind: "thinking" });
        // The buffered event closes the start-only preview.
        setLiveThinkingId((open) => (open === event.id ? null : open));
        return;
      case "agent.thread_message_sent":
        // The planner handed its draft to a roster agent and is waiting on
        // the reply: label the silence. The received event clears it, and so
        // does the planner's next model request.
        setActivity({ kind: "delegating", message: event.to_agent_name ?? undefined });
        return;
      case "agent.thread_message_received":
        setActivity(null);
        return;
      case "span.model_request_start":
        setWorking(true);
        setActivity(null); // a lingering "thinking..." label ends here
        return;
      case "span.model_request_end":
        // An errored request never produces its buffered events, so drop the previews.
        if (event.is_error) {
          setPreview(null);
          setLiveThinkingId(null);
        }
        return;
      case "session.error":
        if (event.error.retry_status.type === "retrying") {
          setActivity({ kind: "retrying", message: event.error.message });
        } else {
          setError(`${event.error.type}: ${event.error.message}`);
        }
        return;
      case "session.status_running":
        setWorking(true);
        return;
      case "session.status_idle":
        setWorking(false);
        setActivity(null);
        setPreview(null);
        setLiveThinkingId(null);
        return;
      case "session.status_terminated":
      case "session.deleted":
        setWorking(false);
        setError(`session ${event.type.split(".")[1]}`);
        return;
      default:
        return;
    }
  }, []);

  // The tail: opened once per session, reopened only by the browser's own
  // EventSource retry.
  useEffect(() => {
    // Fill whatever happened while disconnected, and recover the two states
    // the tail cannot deliver: a `status_idle` that fired in the gap (the
    // `working` field), and a session archived under this tab (the cookie
    // moved on, so reload into the new one).
    const resync = () => {
      void fetch("/api/session", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({}),
      })
        .then((res) => (res.ok ? res.json() : null))
        .then(
          (
            data: {
              sessionId?: string;
              events?: ManagedAgentEvent[];
              working?: boolean;
            } | null,
          ) => {
            if (!data?.sessionId) return;
            if (data.sessionId !== boot.sessionId) {
              window.location.reload();
              return;
            }
            if (data.events) {
              setEvents((current) => mergeLog(data.events as ManagedAgentEvent[], current));
            }
            setWorking(Boolean(data.working));
            // The closing events for these previews may have fired in the
            // gap and arrived only through this fetch, never through apply.
            if (!data.working) {
              setPreview(null);
              setLiveThinkingId(null);
            }
          },
        )
        .catch(() => {}); // the server is down, and the next retry re-syncs
    };
    const source = new EventSource("/api/stream");
    source.onopen = resync;
    source.onerror = resync; // EventSource retries on its own, and this re-syncs between tries
    source.onmessage = (message) =>
      apply(JSON.parse(message.data) as BetaManagedAgentsStreamSessionEvents);
    return () => source.close();
  }, [apply, boot.sessionId]);

  const send = useCallback(async (text: string) => {
    setError(null);
    setWorking(true); // the echo and span events confirm momentarily
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) {
        setWorking(false);
        setError(
          ((await res.json().catch(() => null)) as { error?: string } | null)?.error ??
            "send failed",
        );
      }
    } catch {
      setWorking(false);
      setError("send failed - is the dev server still running?");
    }
  }, []);

  const interrupt = useCallback(async () => {
    await fetch("/api/interrupt", { method: "POST" }).catch(() => {});
    // The session.status_idle that follows flips `working` off.
  }, []);

  const turns: Turn[] = useMemo(
    () => foldTranscript(events, preview, liveThinkingId),
    [events, preview, liveThinkingId],
  );

  return { turns, working, activity, error, clearError: () => setError(null), send, interrupt };
}
