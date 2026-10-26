"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface EmployeeOption {
  id: number;
  name: string;
}

export default function ScheduleOneOnOneForm({ employees }: { employees: EmployeeOption[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [employeeId, setEmployeeId] = useState(employees[0]?.id ?? 0);
  const [scheduledAt, setScheduledAt] = useState("");
  const [agenda, setAgenda] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await fetch("/api/performance/one-on-ones", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          employee_id: employeeId,
          scheduled_at: scheduledAt,
          agenda: agenda || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Something went wrong.");
        return;
      }
      setOpen(false);
      setScheduledAt("");
      setAgenda("");
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
        Schedule 1-on-1
      </button>
    );
  }

  return (
    <form onSubmit={submit} className="card w-full space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Schedule a 1-on-1</h2>
        <button type="button" className="text-sm text-gray-400 hover:text-gray-600" onClick={() => setOpen(false)}>
          ✕ Close
        </button>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="label" htmlFor="oo-employee">Employee</label>
          <select
            id="oo-employee"
            className="input"
            value={employeeId}
            onChange={(e) => setEmployeeId(Number(e.target.value))}
            required
          >
            {employees.map((emp) => (
              <option key={emp.id} value={emp.id}>
                {emp.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="oo-when">Date &amp; time</label>
          <input
            id="oo-when"
            type="datetime-local"
            className="input"
            value={scheduledAt}
            onChange={(e) => setScheduledAt(e.target.value)}
            required
          />
        </div>
      </div>
      <div>
        <label className="label" htmlFor="oo-agenda">Agenda (optional)</label>
        <textarea
          id="oo-agenda"
          className="input"
          rows={3}
          value={agenda}
          onChange={(e) => setAgenda(e.target.value)}
          placeholder="Topics to discuss…"
        />
      </div>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? "Scheduling…" : "Schedule"}
        </button>
        <button type="button" className="btn-secondary" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
  );
}
