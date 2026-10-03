"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChatMessage, WeddingParams } from "@/types/wedding";

const SUMMARY_FIELDS: { key: keyof WeddingParams; label: string }[] = [
  { key: "date", label: "Termín" },
  { key: "venue", label: "Místo" },
  { key: "budget", label: "Rozpočet" },
  { key: "guestCount", label: "Hosté" },
];

export default function ChatWindow({
  params,
  onReset,
}: {
  params: WeddingParams;
  onReset: () => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const initialized = useRef(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    void sendConversation([
      {
        role: "user",
        content:
          "Na základě zadaných parametrů mi prosím sestav kompletní úvodní plán: analýzu, časovou osu příprav, rozpad rozpočtu a minutovník svatebního dne.",
      },
    ]);
    // Fires exactly once on mount to kick off the initial plan; sendConversation
    // is stable in practice and re-running this on every render would resend it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function sendConversation(nextMessages: ChatMessage[]) {
    setMessages(nextMessages);
    setIsStreaming(true);

    const assistantIndex = nextMessages.length;
    let assistantText = "";

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: nextMessages, params }),
      });

      if (!res.body) throw new Error("Odpověď neobsahuje datový proud.");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      setMessages([...nextMessages, { role: "assistant", content: "" }]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        assistantText += decoder.decode(value, { stream: true });
        setMessages((prev) => {
          const updated = [...prev];
          updated[assistantIndex] = {
            role: "assistant",
            content: assistantText,
          };
          return updated;
        });
      }
    } catch (error) {
      console.error(error);
      setMessages((prev) => {
        const updated = [...prev];
        updated[assistantIndex] = {
          role: "assistant",
          content:
            assistantText ||
            "Omlouváme se, došlo k výpadku spojení. Zkuste zprávu odeslat znovu.",
        };
        return updated;
      });
    } finally {
      setIsStreaming(false);
    }
  }

  function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isStreaming) return;
    setInput("");
    void sendConversation([...messages, { role: "user", content: trimmed }]);
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-gold/15 bg-surface/80 px-6 py-4 backdrop-blur">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-gold">
            Svatební koordinátorka
          </p>
          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted">
            {SUMMARY_FIELDS.map(({ key, label }) =>
              params[key] ? (
                <span key={key}>
                  <span className="text-gold-light/80">{label}:</span>{" "}
                  {params[key]}
                </span>
              ) : null,
            )}
          </div>
        </div>
        <button
          onClick={onReset}
          className="rounded-md border border-gold/25 px-3 py-1.5 text-xs uppercase tracking-wider text-gold-light/90 transition hover:bg-gold/10"
        >
          Upravit parametry
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-8">
        <div className="mx-auto flex max-w-3xl flex-col gap-6">
          {messages.map((message, i) => (
            <div
              key={i}
              className={
                message.role === "user"
                  ? "self-end max-w-[85%] rounded-2xl rounded-br-sm bg-gold/15 px-4 py-3 text-sm text-ivory"
                  : "self-start max-w-[95%] rounded-2xl rounded-bl-sm border border-gold/10 bg-card px-5 py-4"
              }
            >
              {message.role === "user" ? (
                <p className="whitespace-pre-wrap">{message.content}</p>
              ) : message.content ? (
                <div className="prose-wedding">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {message.content}
                  </ReactMarkdown>
                </div>
              ) : (
                <div className="flex gap-1.5 py-1">
                  <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-gold [animation-delay:0ms]" />
                  <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-gold [animation-delay:200ms]" />
                  <span className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-gold [animation-delay:400ms]" />
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      <form
        onSubmit={handleSend}
        className="border-t border-gold/15 bg-surface/80 px-4 py-4 backdrop-blur sm:px-8"
      >
        <div className="mx-auto flex max-w-3xl items-end gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend(e);
              }
            }}
            placeholder="Zeptejte se na cokoliv — dodavatele, harmonogram, rozpočet…"
            rows={1}
            className="max-h-32 flex-1 resize-none rounded-lg border border-gold/20 bg-ink/60 px-3.5 py-2.5 text-sm text-ivory placeholder:text-muted/60 focus:border-gold/60 focus:outline-none focus:ring-1 focus:ring-gold/40"
          />
          <button
            type="submit"
            disabled={isStreaming || !input.trim()}
            className="rounded-lg bg-gradient-to-r from-gold-dark via-gold to-gold-light px-5 py-2.5 text-sm font-semibold text-ink transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Odeslat
          </button>
        </div>
      </form>
    </div>
  );
}
