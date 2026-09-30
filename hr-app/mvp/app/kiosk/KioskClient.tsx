"use client";

import { useEffect, useRef, useState } from "react";

type ClockEventType = "clock_in" | "clock_out" | "break_start" | "break_end";

const ACTIONS: { type: ClockEventType; label: string; className: string }[] = [
  { type: "clock_in", label: "Clock in", className: "bg-green-600 hover:bg-green-700" },
  { type: "clock_out", label: "Clock out", className: "bg-red-600 hover:bg-red-700" },
  { type: "break_start", label: "Start break", className: "bg-amber-500 hover:bg-amber-600" },
  { type: "break_end", label: "End break", className: "bg-brand-600 hover:bg-brand-700" },
];

const PAD_KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "clear", "0", "back"] as const;

interface Feedback {
  kind: "success" | "error";
  message: string;
}

export default function KioskClient() {
  const [employeeNumber, setEmployeeNumber] = useState("");
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState<ClockEventType | null>(null);
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [clock, setClock] = useState("");
  const feedbackTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const tick = () =>
      setClock(
        new Date().toLocaleTimeString("en-ZA", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
      );
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => () => {
    if (feedbackTimer.current) clearTimeout(feedbackTimer.current);
  }, []);

  function showFeedback(f: Feedback) {
    if (feedbackTimer.current) clearTimeout(feedbackTimer.current);
    setFeedback(f);
    feedbackTimer.current = setTimeout(() => setFeedback(null), 6000);
  }

  function pressPad(key: (typeof PAD_KEYS)[number]) {
    if (key === "clear") setPin("");
    else if (key === "back") setPin((p) => p.slice(0, -1));
    else setPin((p) => (p.length < 4 ? p + key : p));
  }

  async function act(type: ClockEventType) {
    if (!employeeNumber.trim() || pin.length !== 4 || busy) return;
    setBusy(type);
    try {
      const res = await fetch("/api/kiosk/clock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ employee_number: employeeNumber.trim(), pin, type }),
      });
      const data = (await res.json().catch(() => null)) as
        | { ok?: boolean; first_name?: string; time?: string; action?: string; error?: string }
        | null;
      if (res.ok && data?.ok) {
        showFeedback({
          kind: "success",
          message: `Welcome, ${data.first_name} — ${data.action} at ${data.time}`,
        });
        setEmployeeNumber("");
        setPin("");
      } else {
        showFeedback({ kind: "error", message: data?.error ?? "Something went wrong. Please try again." });
        setPin("");
      }
    } catch {
      showFeedback({ kind: "error", message: "Network error — please try again." });
    } finally {
      setBusy(null);
    }
  }

  const ready = employeeNumber.trim().length > 0 && pin.length === 4;

  return (
    <div className="fixed inset-0 z-50 flex min-h-screen flex-col overflow-y-auto bg-gray-900 text-white">
      <header className="flex items-center justify-between border-b border-gray-800 px-8 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600 text-xl font-bold">H</div>
          <div>
            <p className="text-xl font-bold leading-tight">HRCore</p>
            <p className="text-xs uppercase tracking-widest text-gray-400">Clock kiosk</p>
          </div>
        </div>
        <p className="font-mono text-3xl font-semibold tabular-nums" suppressHydrationWarning>
          {clock}
        </p>
      </header>

      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center gap-8 p-6">
        <div
          role="status"
          aria-live="polite"
          className={`w-full rounded-2xl px-6 py-5 text-center text-2xl font-semibold transition-opacity ${
            feedback
              ? feedback.kind === "success"
                ? "bg-green-600/90"
                : "bg-red-600/90"
              : "bg-gray-800/60 text-gray-400"
          }`}
        >
          {feedback ? feedback.message : "Enter your employee number and PIN, then choose an action."}
        </div>

        <div className="grid w-full gap-8 sm:grid-cols-2">
          <div className="space-y-5">
            <div>
              <label htmlFor="kiosk-emp" className="mb-2 block text-sm font-medium uppercase tracking-wide text-gray-400">
                Employee number
              </label>
              <input
                id="kiosk-emp"
                className="w-full rounded-xl border border-gray-700 bg-gray-800 px-4 py-4 text-center text-2xl font-semibold uppercase tracking-widest text-white focus:border-brand-500 focus:outline-none"
                placeholder="EMP006"
                autoComplete="off"
                value={employeeNumber}
                onChange={(e) => setEmployeeNumber(e.target.value.toUpperCase())}
              />
            </div>

            <div>
              <p className="mb-2 text-sm font-medium uppercase tracking-wide text-gray-400">PIN</p>
              <div className="mb-3 flex justify-center gap-3" aria-label="PIN entry">
                {[0, 1, 2, 3].map((i) => (
                  <span
                    key={i}
                    className={`flex h-5 w-5 items-center justify-center rounded-full border-2 ${
                      pin.length > i ? "border-brand-400 bg-brand-400" : "border-gray-600"
                    }`}
                  />
                ))}
              </div>
              <div className="grid grid-cols-3 gap-2">
                {PAD_KEYS.map((key) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => pressPad(key)}
                    className={`rounded-xl py-4 text-2xl font-semibold transition-colors ${
                      key === "clear" || key === "back"
                        ? "bg-gray-800 text-base text-gray-400 hover:bg-gray-700"
                        : "bg-gray-800 hover:bg-gray-700"
                    }`}
                  >
                    {key === "clear" ? "C" : key === "back" ? "⌫" : key}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="flex flex-col justify-center gap-3">
            {ACTIONS.map((a) => (
              <button
                key={a.type}
                type="button"
                disabled={!ready || busy !== null}
                onClick={() => act(a.type)}
                className={`rounded-2xl px-6 py-6 text-2xl font-bold transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${a.className}`}
              >
                {busy === a.type ? "Working…" : a.label}
              </button>
            ))}
          </div>
        </div>
      </main>

      <footer className="border-t border-gray-800 px-8 py-4 text-center text-xs text-gray-500">
        Acme (Pty) Ltd · Every action requires your employee number and 4-digit PIN. Ask HR if you forgot your PIN.
      </footer>
    </div>
  );
}
