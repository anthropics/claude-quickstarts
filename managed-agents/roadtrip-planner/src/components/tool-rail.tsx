"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { RailItem, ToolCall, TurnStats } from "@/lib/transcript";

/**
 * The evidence rail: the session's event stream, grouped by turn, newest
 * turn first and open. Every event renders as it arrives: model request
 * spans, thinking blocks, the `agent.message` growing delta by delta, and
 * each tool call with the raw output the agent saw.
 *
 * A live event holds itself expanded so the streaming is visible; 500ms
 * after its closing event lands it animates shut. Clicking a row pins it
 * open (or shut) past that.
 */

export type ToolGroup = { id: string; turn: number; items: RailItem[] };

export function commandOf(call: ToolCall): string {
  const input = call.input as Record<string, unknown> | undefined;
  const command = input && typeof input.command === "string" ? input.command : undefined;
  return command ?? `${call.name} ${JSON.stringify(input ?? {})}`.slice(0, 200);
}

export function dotClass(call: ToolCall): string {
  if (call.state === "error") return "dot err";
  if (call.state === "ok") return "dot ok";
  return "dot run";
}

const COLLAPSE_DELAY_MS = 500;

/**
 * Which items hold themselves open: every live item, plus items whose
 * stream just ended and are inside the 500ms linger before the collapse
 * animation runs.
 */
function useLingerOpen(groups: ToolGroup[]): Record<string, boolean> {
  const [linger, setLinger] = useState<Record<string, boolean>>({});
  const timers = useRef<Map<string, number>>(new Map());
  const wasLive = useRef<Set<string>>(new Set());

  // Layout effect, not effect: the render where an item flips live -> done
  // must not paint before linger marks it open, or the panel twitches
  // shut-then-open instead of holding for the 500ms.
  useLayoutEffect(() => {
    const liveNow = new Set<string>();
    for (const group of groups) {
      for (const item of group.items) if (item.live) liveNow.add(item.id);
    }
    for (const id of liveNow) {
      // (Re)opened: cancel a pending collapse from a reconnect blip.
      const timer = timers.current.get(id);
      if (timer !== undefined) {
        clearTimeout(timer);
        timers.current.delete(id);
      }
    }
    for (const id of wasLive.current) {
      if (liveNow.has(id) || timers.current.has(id)) continue;
      setLinger((open) => ({ ...open, [id]: true }));
      const timer = window.setTimeout(() => {
        timers.current.delete(id);
        setLinger(({ [id]: _done, ...rest }) => rest);
      }, COLLAPSE_DELAY_MS);
      timers.current.set(id, timer);
    }
    wasLive.current = liveNow;
  }, [groups]);

  useEffect(() => {
    const pending = timers.current;
    return () => {
      for (const timer of pending.values()) clearTimeout(timer);
    };
  }, []);

  return linger;
}

function itemDotClass(item: RailItem): string {
  if (item.kind === "tool") return dotClass(item.call);
  if (item.live) return "dot run";
  if (item.kind === "model" && item.error) return "dot err";
  return "dot ok";
}

function itemLabel(item: RailItem): string {
  switch (item.kind) {
    case "tool":
      return commandOf(item.call);
    case "model":
      return "span.model_request";
    case "thinking":
      return "agent.thinking";
    case "thread":
      return "session.thread_created";
    case "thread_message":
      return `agent.thread_message_${item.message.direction}`;
  }
}

function itemMeta(item: RailItem): string {
  switch (item.kind) {
    case "tool":
      return item.live ? "running" : "";
    case "model":
      return item.live
        ? "in flight"
        : item.usage
          ? `${item.usage.outputTokens.toLocaleString()} tok out`
          : "";
    case "thinking":
      return item.live ? "streaming" : "";
    case "thread":
      return item.live ? `${item.agentName} running` : item.agentName;
    case "thread_message":
      return item.message.direction === "sent"
        ? `to ${item.message.agentName}`
        : `from ${item.message.agentName}`;
  }
}

function itemBody(item: RailItem): string {
  switch (item.kind) {
    case "tool": {
      const head = `$ ${commandOf(item.call)}`;
      if (item.call.state === "running") return `${head}\n\n(waiting for the result event...)`;
      return `${head}\n\n${item.call.output || (item.call.state === "error" ? "error" : "(no output)")}`;
    }
    case "model":
      if (item.live) {
        return "model request open - agent.message deltas stream into the chat while this span runs";
      }
      if (!item.usage) return item.error ? "errored" : "done";
      return [
        `input tokens   ${item.usage.inputTokens.toLocaleString()}`,
        `output tokens  ${item.usage.outputTokens.toLocaleString()}`,
        `cache read     ${item.usage.cacheReadTokens.toLocaleString()}`,
        `cache write    ${item.usage.cacheCreateTokens.toLocaleString()}`,
      ].join("\n");
    case "thinking":
      return item.live
        ? "event_start arrived - the model is thinking. Thinking previews are start-only: no deltas follow, and the buffered event closes this."
        : "finished (thinking content is never previewed)";
    case "thread":
      return [
        `thread ${item.threadId}`,
        `agent  "${item.agentName}"`,
        "",
        item.live
          ? "spawned by the coordinator and running - its thread_status events cross-post to this stream"
          : "finished (the thread's own transcript is its event log, scoped by the sthr_ id)",
      ].join("\n");
    case "thread_message":
      return item.message.text || "(no text content)";
  }
}

function Chevron() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 6l6 6-6 6" />
    </svg>
  );
}

function Caret() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

export function ToolRail({
  className,
  groups,
  openGroups,
  openCalls,
  onToggleGroup,
  onToggleCall,
  stats,
}: {
  className: string;
  groups: ToolGroup[];
  openGroups: Record<string, boolean>;
  openCalls: Record<string, boolean>;
  onToggleGroup: (id: string, open: boolean) => void;
  onToggleCall: (id: string, open: boolean) => void;
  stats: TurnStats | undefined;
}) {
  const linger = useLingerOpen(groups);

  // New events land at the bottom: stay glued to them while something is
  // streaming, unless the reader has scrolled up to inspect something (then
  // stick when they come back down). Gating on a live item keeps a chip
  // click (which re-renders the rail to reveal an older card) from
  // scrolling the revealed card away.
  const bodyRef = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const anyLive = groups.some((group) => group.items.some((item) => item.live));
  useEffect(() => {
    const el = bodyRef.current;
    if (!el || !stick.current || !anyLive) return;
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
    });
  }, [groups, linger, anyLive]);
  const onBodyScroll = () => {
    const el = bodyRef.current;
    if (el) stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 90;
  };

  return (
    <aside className={className}>
      <div className="rhead">
        <h2 className="rtitle">Session events</h2>
        <p className="rexp">
          The stream, as it arrives: model request spans, thinking blocks, every{" "}
          <code>curl</code> the agent runs in its sandbox, and the messages it trades with the
          reviewer thread (the reply itself streams in the chat). A live event stays open. It
          folds shut when its closing event lands.
        </p>
      </div>
      <div className="rbody" ref={bodyRef} onScroll={onBodyScroll}>
        {groups.length === 0 && <p className="rnone">Nothing yet.</p>}
        {groups.map((group, index) => {
          // the newest turn (the last one) starts open, everything else collapsed
          const open = openGroups[group.id] ?? index === groups.length - 1;
          return (
            <div className="grp" key={group.id}>
              <button type="button" className="ghead" onClick={() => onToggleGroup(group.id, open)}>
                <span className={open ? "gcar gco" : "gcar"}>
                  <Chevron />
                </span>
                turn {group.turn}
                <span className="gline" />
                <span className="gn">
                  {group.items.length} {group.items.length === 1 ? "event" : "events"}
                </span>
              </button>
              {open &&
                group.items.map((item) => {
                  // A click pins the row open or shut; otherwise live events
                  // (and the 500ms linger after they close) hold it open.
                  const expanded = openCalls[item.id] ?? (item.live || linger[item.id] === true);
                  const label = itemLabel(item);
                  return (
                    <div className="tcc" key={item.id}>
                      <button
                        type="button"
                        className="tcrow"
                        title={label}
                        onClick={() => onToggleCall(item.id, expanded)}
                      >
                        <span className={itemDotClass(item)} />
                        <span className={item.kind === "tool" ? "cmd" : "cmd evt"}>{label}</span>
                        {itemMeta(item) && <span className="imeta">{itemMeta(item)}</span>}
                        <span className={expanded ? "car up" : "car"}>
                          <Caret />
                        </span>
                      </button>
                      <div className={expanded ? "acc open" : "acc"}>
                        <div className="accin">
                          <div className="tcbody">
                            <pre
                              className={
                                item.kind === "tool" && item.call.state === "error"
                                  ? "pre pre-err"
                                  : "pre"
                              }
                            >
                              {itemBody(item)}
                            </pre>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
            </div>
          );
        })}
      </div>
      {stats && (
        <p className="sfoot">
          last turn: {stats.modelRequests} model requests, {stats.toolCalls} tool calls,{" "}
          {(stats.inputTokens + stats.outputTokens).toLocaleString()} tokens
        </p>
      )}
    </aside>
  );
}
