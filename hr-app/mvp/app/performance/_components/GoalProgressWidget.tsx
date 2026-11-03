"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Props {
  goalId: number;
  metricType: "percentage" | "number" | "boolean";
  currentValue: number;
  targetValue: number;
  status: string;
}

const STATUSES = [
  { value: "not_started", label: "Not started" },
  { value: "in_progress", label: "In progress" },
  { value: "at_risk", label: "At risk" },
  { value: "achieved", label: "Achieved" },
  { value: "missed", label: "Missed" },
];

export default function GoalProgressWidget({ goalId, metricType, currentValue, targetValue, status }: Props) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState(String(currentValue));
  const [done, setDone] = useState(currentValue >= targetValue);
  const [nextStatus, setNextStatus] = useState(status);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save() {
    setError(null);
    setBusy(true);
    try {
      const res = await fetch(`/api/performance/goals/${goalId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_value: metricType === "boolean" ? (done ? targetValue : 0) : Number(value),
          status: nextStatus,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Failed to update goal.");
        return;
      }
      setOpen(false);
      router.refresh();
    } catch {
      setError("Network error — please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button className="text-sm font-medium text-brand-600 hover:underline" onClick={() => setOpen(true)}>
        Update progress
      </button>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {metricType === "boolean" ? (
          <label className="flex items-center gap-1.5 text-sm text-gray-700">
            <input type="checkbox" checked={done} onChange={(e) => setDone(e.target.checked)} />
            Done
          </label>
        ) : (
          <input
            type="number"
            step="any"
            min="0"
            className="input w-28"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            aria-label="Current value"
          />
        )}
        <select
          className="input w-36"
          value={nextStatus}
          onChange={(e) => setNextStatus(e.target.value)}
          aria-label="Goal status"
        >
          {STATUSES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
        <button className="btn-primary text-sm" onClick={save} disabled={busy}>
          {busy ? "Saving…" : "Save"}
        </button>
        <button className="btn-secondary text-sm" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
