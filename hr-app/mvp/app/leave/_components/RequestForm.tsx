"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface LeaveTypeOption {
  id: number;
  name: string;
  colour: string;
}

export default function RequestForm({ leaveTypes }: { leaveTypes: LeaveTypeOption[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [leaveTypeId, setLeaveTypeId] = useState(leaveTypes[0]?.id ?? 0);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [startHalf, setStartHalf] = useState(false);
  const [endHalf, setEndHalf] = useState(false);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const singleDay = Boolean(startDate) && startDate === endDate;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await fetch("/api/leave/requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          leave_type_id: leaveTypeId,
          start_date: startDate,
          end_date: endDate,
          start_half: startHalf,
          end_half: singleDay ? false : endHalf,
          notes: notes || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Something went wrong.");
        return;
      }
      setOpen(false);
      setStartDate("");
      setEndDate("");
      setStartHalf(false);
      setEndHalf(false);
      setNotes("");
      router.refresh();
    } catch {
      setError("Network error — please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button className="btn-primary" onClick={() => setOpen(true)}>
        Request leave
      </button>
    );
  }

  return (
    <form onSubmit={submit} className="card w-full space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">New leave request</h2>
        <button type="button" className="text-sm text-gray-400 hover:text-gray-600" onClick={() => setOpen(false)}>
          ✕ Close
        </button>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <div>
          <label className="label" htmlFor="lr-type">Leave type</label>
          <select
            id="lr-type"
            className="input"
            value={leaveTypeId}
            onChange={(e) => setLeaveTypeId(Number(e.target.value))}
          >
            {leaveTypes.map((lt) => (
              <option key={lt.id} value={lt.id}>
                {lt.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="lr-start">Start date</label>
          <input
            id="lr-start"
            type="date"
            className="input"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="lr-end">End date</label>
          <input
            id="lr-end"
            type="date"
            className="input"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            required
          />
        </div>
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-2">
        {singleDay ? (
          <label className="inline-flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
              checked={startHalf}
              onChange={(e) => setStartHalf(e.target.checked)}
            />
            Half day
          </label>
        ) : (
          <>
            <label className="inline-flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
                checked={startHalf}
                onChange={(e) => setStartHalf(e.target.checked)}
              />
              First day is a half day (afternoon)
            </label>
            <label className="inline-flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
                checked={endHalf}
                onChange={(e) => setEndHalf(e.target.checked)}
              />
              Last day is a half day (morning)
            </label>
          </>
        )}
      </div>
      <div>
        <label className="label" htmlFor="lr-notes">Notes (optional)</label>
        <input
          id="lr-notes"
          className="input"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="e.g. Family holiday"
        />
      </div>
      <p className="text-xs text-gray-400">
        Weekends and public holidays are excluded automatically; working days are calculated on submission.
      </p>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? "Submitting…" : "Submit request"}
        </button>
        <button type="button" className="btn-secondary" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
  );
}
