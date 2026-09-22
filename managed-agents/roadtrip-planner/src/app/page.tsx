"use client";

import { useEffect, useRef, useState } from "react";
import { Mark } from "@/components/mark";
import { Markdown } from "@/components/markdown";
import { MODELS } from "@/lib/models";
import { ToolRail, type ToolGroup, commandOf, dotClass } from "@/components/tool-rail";
import type { ManagedAgentEvent, Turn } from "@/lib/transcript";
import { useManagedAgentSession, type Activity } from "@/lib/use-managed-agent-session";

/**
 * The page. All the chat mechanics live in `useManagedAgentSession` (one event
 * stream, the SDK accumulator, one fold). This file is the rendering and
 * nothing else. There is no chat framework: the session's event log is the
 * message list.
 */

type Boot = { sessionId: string; events: ManagedAgentEvent[]; model: string | null; working: boolean };

/**
 * The header picker offers MODELS. Picking one starts a new trip whose
 * session is created with the `agent_with_overrides` selector: the same
 * stored agent, its model replaced for that session only. The stored agent
 * (and what `./agents/setup.sh` provisioned) never changes.
 */

const SUGGESTIONS = [
  "Plan a 5 day road trip split between Zion and Bryce Canyon for the first week of October. We're car camping the whole way.",
  "Which Acadia campgrounds can I still book this week, and is anything closed right now?",
  "What does the weather look like at Yellowstone over the next 3 days, hour by hour for the mornings?",
];

/** Below 880px the rail becomes a drawer and the header drops its wide-only items. */
function useNarrow(): boolean {
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(max-width: 880px)");
    const update = () => setNarrow(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return narrow;
}

export default function Page() {
  const [boot, setBoot] = useState<Boot | null>(null);
  const [bootError, setBootError] = useState<string | null>(null);
  const started = useRef(false); // strict mode runs effects twice in dev

  const start = async (fresh: boolean, model?: string) => {
    setBoot(null);
    setBootError(null);
    try {
      // A trip abandoned mid-answer should not keep the agent working.
      if (fresh) await fetch("/api/interrupt", { method: "POST" }).catch(() => {});
      const res = await fetch("/api/session", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ fresh, model }),
      });
      if (!res.ok) throw new Error(await res.text());
      setBoot((await res.json()) as Boot);
    } catch (error) {
      setBootError(error instanceof Error ? error.message : String(error));
    }
  };

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void start(false);
  }, []);

  if (bootError) {
    return (
      <main className="boot">
        <Mark size={44} />
        <h1 className="btitle">Road trip planner</h1>
        <p className="bmsg">The session could not start.</p>
        <pre className="berr">{bootError}</pre>
        <p className="bhint">
          Most likely the agent has not been provisioned yet: run <code>./agents/setup.sh</code>{" "}
          (its <code>ant apply</code> writes the ids into <code>claude-lock.json</code>), then restart{" "}
          <code>npm run dev</code>.
        </p>
        <button type="button" className="newbtn" onClick={() => void start(false)}>
          Retry
        </button>
      </main>
    );
  }
  if (!boot) {
    return (
      <main className="boot">
        <Mark size={44} />
        <h1 className="btitle">Road trip planner</h1>
        <span className="bspin" />
        <p className="bmsg">
          Starting your session (the sandbox warms up now, not on your first question)...
        </p>
      </main>
    );
  }
  return <Trip key={boot.sessionId} boot={boot} onNewTrip={(model) => void start(true, model)} />;
}

function Trip({ boot, onNewTrip }: { boot: Boot; onNewTrip: (model?: string) => void }) {
  const [input, setInput] = useState("");
  const [drawer, setDrawer] = useState(false);
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  const [openCalls, setOpenCalls] = useState<Record<string, boolean>>({});
  const narrow = useNarrow();

  const { turns, working, activity, error, clearError, send, interrupt } = useManagedAgentSession({
    sessionId: boot.sessionId,
    events: boot.events,
    working: boot.working,
  });

  const lastTurn = turns[turns.length - 1];
  const replyStarted = !!lastTurn && lastTurn.parts.length > 0;

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const submit = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || working) return;
    setInput("");
    const el = textareaRef.current;
    if (el) el.style.height = "auto";
    void send(trimmed);
  };

  // Stay glued to the newest token only while the reader is already at the
  // bottom. Scrolling up to re-read mid-answer sticks until they come back.
  const threadRef = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  useEffect(() => {
    const el = threadRef.current;
    if (!el || !stick.current) return;
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
    });
  }, [turns]);
  const onThreadScroll = () => {
    const el = threadRef.current;
    if (el) stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 90;
  };

  // The rail groups the event timeline by turn, in conversation order.
  const groups: ToolGroup[] = turns
    .map((turn, index) => ({ id: turn.id, turn: index + 1, items: turn.rail }))
    .filter((group) => group.items.length > 0);
  const toolTotal = groups.reduce(
    (total, group) => total + group.items.filter((item) => item.kind === "tool").length,
    0,
  );
  const anyRunning = groups.some((group) => group.items.some((item) => item.live));
  const lastStats = turns.findLast((turn) => turn.stats.modelRequests > 0)?.stats;

  // An inline chip opens its own card in the rail (and the drawer when narrow).
  const reveal = (groupId: string, callId: string) => {
    setOpenGroups((open) => ({ ...open, [groupId]: true }));
    setOpenCalls((open) => ({ ...open, [callId]: true }));
    if (narrow) setDrawer(true);
  };

  const hasContent = turns.some((turn) => turn.userText || turn.parts.length > 0);

  return (
    <div className="app">
      <header className={narrow ? "hdr nh" : "hdr"}>
        <Mark />
        <h1 className="title">Road trip planner</h1>
        {!narrow && (
          <span className="sid" title={boot.sessionId}>
            {boot.sessionId}
          </span>
        )}
        <span className="hsp" />
        {!narrow && boot.model && (
          <label
            className="msel"
            title="The model this session runs on. Picking another starts a new trip created with agent_with_overrides: same stored agent, different model, this session only."
          >
            <select
              value={boot.model}
              onChange={(e) => onNewTrip(e.target.value)}
              aria-label="model for the next trip"
            >
              {((MODELS as readonly string[]).includes(boot.model) ? MODELS : [boot.model, ...MODELS]).map((model) => (
                <option key={model} value={model}>
                  {model.replace(/^claude-/, "")}
                </option>
              ))}
            </select>
          </label>
        )}
        {narrow && (
          <button type="button" className="toolsbtn" onClick={() => setDrawer((open) => !open)}>
            <span className={anyRunning ? "dot run" : "dot ok"} />
            Tools
            <span className="tcount">{toolTotal}</span>
          </button>
        )}
        <button type="button" className="newbtn" onClick={() => onNewTrip()}>
          New trip
        </button>
      </header>

      <main className="main">
        <section className="chatcol">
          <div className="thread" ref={threadRef} onScroll={onThreadScroll}>
            <div className="tin">
              {!hasContent && (
                <div className="empt">
                  <h2 className="eled">Where to, and when?</h2>
                  <p className="esub">
                    Every fact comes from the National Park Service and Windy APIs, called from a
                    sandbox with keys it cannot read.
                  </p>
                  <div className="sug">
                    {SUGGESTIONS.map((suggestion) => (
                      <button
                        key={suggestion}
                        type="button"
                        className="sugc"
                        onClick={() => submit(suggestion)}
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {turns.map((turn) => (
                <TurnView key={turn.id} turn={turn} onChipClick={(callId) => reveal(turn.id, callId)} />
              ))}
              {working && (
                <p className="act">
                  <span className="actdot" />
                  {activityLabel(activity, replyStarted)}
                </p>
              )}
              {error && (
                <div className="eline">
                  <span className="f1">{error}</span>
                  <button type="button" className="dismiss" onClick={clearError}>
                    dismiss
                  </button>
                </div>
              )}
              <div className="bpad" />
            </div>
          </div>

          <div className="comp">
            <form
              className="cbox"
              onSubmit={(e) => {
                e.preventDefault();
                submit(input);
              }}
            >
              <textarea
                ref={textareaRef}
                className="ta"
                value={input}
                rows={2}
                placeholder='Try: "swap day 2 and 3, and we have a dog"'
                onChange={(e) => {
                  setInput(e.target.value);
                  const el = e.currentTarget;
                  el.style.height = "auto";
                  el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    submit(input);
                  }
                }}
              />
              {working ? (
                <button
                  type="button"
                  className="stopb"
                  aria-label="stop"
                  title="Sends a user.interrupt event: the agent actually stops"
                  onClick={() => void interrupt()}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                    <rect x="5" y="5" width="14" height="14" rx="3" />
                  </svg>
                </button>
              ) : (
                <button
                  type="submit"
                  className={input.trim() ? "sendb" : "sendb off"}
                  aria-label="send"
                  disabled={!input.trim()}
                >
                  <svg
                    width="17"
                    height="17"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M12 19V5" />
                    <path d="M5 12l7-7 7 7" />
                  </svg>
                </button>
              )}
            </form>
          </div>
        </section>

        {narrow && drawer && (
          <button
            type="button"
            className="scrim"
            aria-label="close tool calls"
            onClick={() => setDrawer(false)}
          />
        )}
        <ToolRail
          className={narrow ? `rail drw${drawer ? " opn" : ""}` : "rail"}
          groups={groups}
          openGroups={openGroups}
          openCalls={openCalls}
          onToggleGroup={(id, open) => setOpenGroups((state) => ({ ...state, [id]: !open }))}
          onToggleCall={(id, open) => setOpenCalls((state) => ({ ...state, [id]: !open }))}
          stats={lastStats}
        />
      </main>
    </div>
  );
}

function TurnView({ turn, onChipClick }: { turn: Turn; onChipClick: (callId: string) => void }) {
  return (
    <>
      {turn.userText && <div className="um">{turn.userText}</div>}
      {turn.parts.length > 0 && (
        <article className="am">
          <div className="ahead">
            <Mark size={16} />
            <span className="alab">Agent</span>
          </div>
          {turn.parts.map((part) => {
            if (part.kind === "text") {
              return <Markdown key={part.id} text={part.text} streaming={part.streaming} />;
            }
            if (part.kind === "thread_message") {
              // One side of the planner/reviewer exchange. The chip names the
              // direction; the full message text is its card in the rail.
              const { message } = part;
              return (
                <button
                  key={message.id}
                  type="button"
                  className="chipt"
                  title={message.text.slice(0, 200)}
                  onClick={() => onChipClick(message.id)}
                >
                  <span className="dot ok" />
                  <span className="tname">
                    {message.direction === "sent"
                      ? `to ${message.agentName}`
                      : `from ${message.agentName}`}
                  </span>
                  <span className="tcmd">{firstLine(message.text)}</span>
                </button>
              );
            }
            return (
              <button
                key={part.call.id}
                type="button"
                className="chipt"
                title={commandOf(part.call)}
                onClick={() => onChipClick(part.call.id)}
              >
                <span className={dotClass(part.call)} />
                <span className="tname">{part.call.name}</span>
                <span className="tcmd">$ {commandOf(part.call)}</span>
              </button>
            );
          })}
        </article>
      )}
    </>
  );
}

function firstLine(text: string): string {
  const line = text.split("\n", 1)[0] ?? "";
  return line.length > 120 ? `${line.slice(0, 120)}...` : line;
}

function activityLabel(activity: Activity | null, replyStarted: boolean): string {
  if (activity?.kind === "retrying") return `retrying: ${activity.message ?? "transient error"}`;
  if (activity?.kind === "thinking") return "thinking...";
  if (activity?.kind === "delegating")
    return `waiting on ${activity.message ?? "a teammate agent"}...`;
  if (!replyStarted) return "waiting for the first token...";
  return "working...";
}
