"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

type ClockState = "out" | "in" | "on_break";
type ClockEventType = "clock_in" | "clock_out" | "break_start" | "break_end";

interface Props {
  state: ClockState;
  /** HH:MM of the event that put the user in the current state (clock_in / break_start). */
  sinceTime: string | null;
}

const STATE_DISPLAY: Record<ClockState, { label: (since: string | null) => string; badge: string; dot: string }> = {
  out: { label: () => "Out", badge: "badge-gray", dot: "bg-gray-400" },
  in: { label: (s) => (s ? `In since ${s}` : "In"), badge: "badge-green", dot: "bg-green-500" },
  on_break: { label: (s) => (s ? `On break since ${s}` : "On break"), badge: "badge-yellow", dot: "bg-yellow-500" },
};

const ACTIONS: Record<ClockState, { type: ClockEventType; label: string; className: string }[]> = {
  out: [{ type: "clock_in", label: "Clock in", className: "btn-primary" }],
  in: [
    { type: "break_start", label: "Start break", className: "btn-secondary" },
    { type: "clock_out", label: "Clock out", className: "btn-danger" },
  ],
  on_break: [{ type: "break_end", label: "End break", className: "btn-primary" }],
};

export default function ClockWidget({ state, sinceTime }: Props) {
  const router = useRouter();
  const [pending, setPending] = useState<ClockEventType | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function act(type: ClockEventType) {
    setPending(type);
    setError(null);
    try {
      const res = await fetch("/api/time/clock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type }),
      });
      if (!res.ok) {
        const data = (await res.json().catch(() => null)) as { error?: string } | null;
        setError(data?.error ?? "Something went wrong.");
      }
      router.refresh();
    } finally {
      setPending(null);
    }
  }

  const display = STATE_DISPLAY[state];
  return (
    <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <span className={`h-3.5 w-3.5 rounded-full ${display.dot}`} aria-hidden />
        <p className="text-3xl font-bold">{display.label(sinceTime)}</p>
      </div>
      <div className="flex flex-col items-start gap-2 sm:items-end">
        <div className="flex gap-2">
          {ACTIONS[state].map((a) => (
            <button
              key={a.type}
              className={a.className}
              disabled={pending !== null}
              onClick={() => act(a.type)}
            >
              {pending === a.type ? "Saving…" : a.label}
            </button>
          ))}
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>
    </div>
  );
}
