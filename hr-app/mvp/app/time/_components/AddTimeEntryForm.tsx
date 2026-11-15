"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Props {
  minDate: string; // oldest correctable date (14 days back)
  maxDate: string; // today
}

export default function AddTimeEntryForm({ minDate, maxDate }: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [date, setDate] = useState(maxDate);
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [breakMinutes, setBreakMinutes] = useState("0");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await fetch("/api/time/entries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          date,
          start_time: startTime,
          end_time: endTime,
          break_minutes: Number(breakMinutes) || 0,
          reason,
        }),
      });
      const data = (await res.json().catch(() => null)) as { error?: string } | null;
      if (!res.ok) {
        setError(data?.error ?? "Something went wrong.");
        return;
      }
      setOpen(false);
      setStartTime("");
      setEndTime("");
      setBreakMinutes("0");
      setReason("");
      router.refresh();
    } catch {
      setError("Network error — please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button className="btn-secondary" onClick={() => setOpen(true)}>
        Add missing time
      </button>
    );
  }

  return (
    <form onSubmit={submit} className="card w-full space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Add missing time</h2>
        <button type="button" className="text-sm text-gray-400 hover:text-gray-600" onClick={() => setOpen(false)}>
          ✕ Close
        </button>
      </div>
      <div className="grid gap-4 sm:grid-cols-4">
        <div>
          <label className="label" htmlFor="mte-date">Date</label>
          <input
            id="mte-date"
            type="date"
            className="input"
            value={date}
            min={minDate}
            max={maxDate}
            onChange={(e) => setDate(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="mte-start">Start</label>
          <input
            id="mte-start"
            type="time"
            className="input"
            value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="mte-end">End</label>
          <input
            id="mte-end"
            type="time"
            className="input"
            value={endTime}
            onChange={(e) => setEndTime(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="mte-break">Break (minutes)</label>
          <input
            id="mte-break"
            type="number"
            min={0}
            step={5}
            className="input"
            value={breakMinutes}
            onChange={(e) => setBreakMinutes(e.target.value)}
          />
        </div>
      </div>
      <div>
        <label className="label" htmlFor="mte-reason">Reason</label>
        <input
          id="mte-reason"
          className="input"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="e.g. Forgot to clock in — customer site visit"
          required
        />
      </div>
      <p className="text-xs text-gray-400">
        Corrections are limited to the last 14 days and need your manager&apos;s approval before they count towards your hours.
      </p>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? "Submitting…" : "Submit for approval"}
        </button>
        <button type="button" className="btn-secondary" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
  );
}
