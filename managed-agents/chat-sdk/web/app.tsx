// Browser chat client. The sidebar lists Managed Agents sessions -- the only
// conversation store there is -- and picking one replays its transcript from
// the session's event log (/api/history). `useChat` POSTs the active
// conversation to /api/chat and reads the AI SDK message stream off the
// response; the server holds that response open for the whole agent turn,
// and every Managed Agents event_delta preview lands here as its own
// text-delta, so the brief types itself out. /api/activity is a second,
// message-free stream: the tool calls, model requests, and retries the
// bridge observes while it works.

import { memo, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import Markdown from "react-markdown";
import { useChat, type UIMessage } from "@chat-adapter/web/react";
// Bundled into the page (esbuild, served as /app.js): the same card shape and formatting the
// server uses, so live cards, replayed cards, and this renderer can't drift.
import {
  consoleTraceUrl,
  formatDuration,
  truncate,
  TITLE_MAX,
  type BriefStats,
} from "../src/brief";

type Activity = { kind: string; label: string };
type SessionSummary = { id: string; title: string; status: string; created_at: string };

const EMPTY_COUNTS = { tools: 0, requests: 0 };

// The bridge closes each research turn with a Chat SDK card; the web adapter
// delivers its fallbackText, a fenced ```card block of JSON. Only a message
// that is exactly that fence renders as a card, and the payload is validated
// strictly (the session ID becomes a link) -- agent-authored text that
// merely resembles a card can at worst draw a cosmetic box pointing at the
// Anthropic Console.
const CARD_MESSAGE = /^```card\n(.*)\n```$/s;
const SESSION_ID = /^[A-Za-z0-9_-]{4,128}$/;

function parseBriefStats(text: string): BriefStats | null {
  const match = CARD_MESSAGE.exec(text.trim());
  if (!match) return null;
  try {
    const value = JSON.parse(match[1]) as Partial<BriefStats>;
    if (
      typeof value.searches === "number" &&
      typeof value.seconds === "number" &&
      typeof value.sessionId === "string" &&
      SESSION_ID.test(value.sessionId)
    ) {
      return value as BriefStats;
    }
  } catch {}
  return null;
}

function BriefCard({ stats }: { stats: BriefStats }) {
  return (
    <aside className="brief-card">
      <p className="brief-title">Brief ready</p>
      <p className="brief-meta">
        {stats.searches} web search{stats.searches === 1 ? "" : "es"} · {formatDuration(stats.seconds)}
      </p>
      <a href={consoleTraceUrl(stats.sessionId)} target="_blank" rel="noreferrer">
        Open session trace
      </a>
    </aside>
  );
}

// Markdown parsing is the expensive part of a render; memo keeps a streaming
// delta or an activity line from re-parsing every bubble in the transcript.
const Bubble = memo(function Bubble({ role, text }: { role: string; text: string }) {
  const stats = role === "assistant" ? parseBriefStats(text) : null;
  if (stats) return <BriefCard stats={stats} />;
  return (
    <article className={role}>
      <Markdown>{text}</Markdown>
    </article>
  );
});

// Live progress for this conversation, isolated from the transcript so feed
// events never re-render the messages. Shows the last few lines while a turn
// runs and a count afterward. Counts are tallied as items arrive (not from
// the trimmed display list), so long turns are not undercounted.
function ActivityFeed({ conversationId, busy }: { conversationId: string; busy: boolean }) {
  const [items, setItems] = useState<(Activity & { key: number })[]>([]);
  const [counts, setCounts] = useState(EMPTY_COUNTS);
  const nextKey = useRef(0);

  useEffect(() => {
    const source = new EventSource(`/api/activity?conversation=${encodeURIComponent(conversationId)}`);
    source.onmessage = (event) => {
      const item = JSON.parse(event.data) as Activity;
      setCounts((current) => ({
        tools: current.tools + (item.kind === "tool" ? 1 : 0),
        requests: current.requests + (item.kind === "model" ? 1 : 0),
      }));
      setItems((current) => [...current, { ...item, key: nextKey.current++ }].slice(-6));
    };
    return () => source.close();
  }, [conversationId]);

  // A new turn starts: drop the previous turn's feed.
  useEffect(() => {
    if (busy) {
      setItems([]);
      setCounts(EMPTY_COUNTS);
    }
  }, [busy]);

  if (busy) {
    return (
      <div className="working">
        <p className="pulse">researching</p>
        <ul className="activity">
          {items.map((item) => (
            <li key={item.key} className={item.kind}>
              {item.label}
            </li>
          ))}
        </ul>
      </div>
    );
  }
  if (counts.tools + counts.requests === 0) return null;
  return (
    <p className="summary">
      {counts.tools} tool call{counts.tools === 1 ? "" : "s"} · {counts.requests} model request
      {counts.requests === 1 ? "" : "s"}
    </p>
  );
}

// One open conversation. Keyed by session ID in App, so switching sessions
// remounts with a fresh useChat whose conversation ID is the session ID and
// whose initial messages are the replayed transcript.
function Conversation({
  sessionId,
  history,
  onFirstMessage,
}: {
  sessionId: string;
  history: UIMessage[];
  onFirstMessage: (title: string) => void;
}) {
  const { messages, sendMessage, stop, status, error } = useChat({
    threadId: sessionId,
    messages: history,
  });
  const [input, setInput] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  // The whole turn is one response: "streaming" covers the minutes between
  // the acknowledgment and the brief, so it doubles as the progress indicator.
  const busy = status === "submitted" || status === "streaming";

  useEffect(() => {
    endRef.current?.scrollIntoView();
  }, [messages, status]);

  return (
    <>
      <section className="transcript">
        {messages.length === 0 && <p className="hint">Try: give me a brief on solid-state batteries</p>}
        {messages.map((message) =>
          message.parts.map(
            (part, index) =>
              part.type === "text" &&
              part.text && (
                <Bubble key={`${message.id}-${index}`} role={message.role} text={part.text} />
              ),
          ),
        )}
        <ActivityFeed conversationId={sessionId} busy={busy} />
        {status === "error" && (
          <p className="error">{error?.message ?? "Something broke."} Check the server log.</p>
        )}
        <div ref={endRef} />
      </section>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          const text = input.trim();
          if (!text || busy) return;
          setInput("");
          // The first message of a fresh conversation doubles as its title:
          // the bridge writes it onto the Managed Agents session, so the
          // sidebar and the Console show it too.
          const first = messages.length === 0;
          void sendMessage({ text, metadata: first ? { title: text } : undefined });
          if (first) onFirstMessage(text);
        }}
      >
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="ask for a brief on any topic"
          autoFocus
        />
        {busy ? (
          // Stop only abandons the response: the research turn keeps running
          // server-side, and a re-sent message queues behind it (see skill.md).
          <button type="button" onClick={() => void stop()}>
            Stop
          </button>
        ) : (
          <button type="submit" disabled={!input.trim()}>
            Send
          </button>
        )}
      </form>
    </>
  );
}

function App() {
  const [sessions, setSessions] = useState<SessionSummary[] | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [history, setHistory] = useState<UIMessage[] | null>(null);
  const [pending, setPending] = useState(false);
  const [fault, setFault] = useState<string | null>(null);

  useEffect(() => {
    void fetch("/api/sessions")
      .then((response) => response.json())
      .then((fetched: SessionSummary[]) =>
        // Merge instead of replace: a chat started while this GET was in
        // flight is already in the list and must not be clobbered.
        setSessions((current) => {
          const seen = new Set((current ?? []).map((session) => session.id));
          return [...(current ?? []), ...fetched.filter((session) => !seen.has(session.id))];
        }),
      )
      .catch(() => setSessions((current) => current ?? []));
  }, []);

  const newChat = async () => {
    if (pending) return;
    setPending(true);
    try {
      const response = await fetch("/api/sessions", { method: "POST" });
      if (!response.ok) throw new Error(`sessions ${response.status}`);
      const session = (await response.json()) as SessionSummary;
      setSessions((current) => [session, ...(current ?? [])]);
      setHistory([]);
      setActive(session.id);
      setFault(null);
    } catch (err) {
      // Leave the current conversation alone; say why the button didn't take.
      console.error("new chat failed", err);
      setFault("Couldn't create a session. Check the server log.");
    } finally {
      setPending(false);
    }
  };

  const openSession = async (id: string) => {
    if (pending || id === active) return;
    setPending(true);
    try {
      const response = await fetch(`/api/history?conversation=${encodeURIComponent(id)}`);
      if (!response.ok) throw new Error(`history ${response.status}`);
      setHistory((await response.json()) as UIMessage[]);
      setActive(id);
      setFault(null);
    } catch (err) {
      // Keep whatever conversation is open instead of blanking the pane.
      console.error("open session failed", err);
      setFault("Couldn't open that conversation. It may have been archived; check the server log.");
    } finally {
      setPending(false);
    }
  };

  const retitle = (id: string, title: string) => {
    // Optimistic mirror of the title the bridge persists (same truncation).
    const short = truncate(title, TITLE_MAX);
    setSessions((current) =>
      (current ?? []).map((session) => (session.id === id ? { ...session, title: short } : session)),
    );
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <header>
          <h1>Research analyst</h1>
          <p>Chat SDK × Claude Managed Agents</p>
        </header>
        <button className="new-chat" onClick={() => void newChat()} disabled={pending}>
          New chat
        </button>
        <nav>
          {sessions === null && <p className="hint">loading sessions...</p>}
          {sessions?.map((session) => (
            <button
              key={session.id}
              className={session.id === active ? "session active" : "session"}
              onClick={() => void openSession(session.id)}
              disabled={pending}
            >
              <span className="title">{session.title}</span>
              <span className="when">{new Date(session.created_at).toLocaleDateString()}</span>
            </button>
          ))}
        </nav>
        {fault && <p className="error">{fault}</p>}
        <p className="sidenote">
          Each conversation is a Managed Agents session. The server stores nothing: restart it, and
          this list -- and every transcript -- comes back from the sessions API.
        </p>
      </aside>

      <main>
        {active && history ? (
          <Conversation
            key={active}
            sessionId={active}
            history={history}
            onFirstMessage={(title) => retitle(active, title)}
          />
        ) : (
          <section className="empty">
            <h2>Name a topic or ask a question.</h2>
            <p>Briefs take a few minutes; the feed shows the research as it happens.</p>
            <button onClick={() => void newChat()} disabled={pending}>
              Start a chat
            </button>
          </section>
        )}
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
