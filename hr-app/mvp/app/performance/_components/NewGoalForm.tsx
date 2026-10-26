"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface EmployeeOption {
  id: number;
  name: string;
}

/**
 * `employees` is empty for regular employees (goal is created for
 * themselves); managers get self + direct reports, HR gets everyone.
 */
export default function NewGoalForm({ employees }: { employees: EmployeeOption[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [type, setType] = useState("individual");
  const [metricType, setMetricType] = useState("percentage");
  const [targetValue, setTargetValue] = useState("100");
  const [dueDate, setDueDate] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await fetch("/api/performance/goals", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          description: description || undefined,
          employee_id: employeeId || undefined,
          type,
          metric_type: metricType,
          target_value: metricType === "boolean" ? 1 : Number(targetValue),
          due_date: dueDate || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Something went wrong.");
        return;
      }
      setOpen(false);
      setTitle("");
      setDescription("");
      setEmployeeId("");
      setType("individual");
      setMetricType("percentage");
      setTargetValue("100");
      setDueDate("");
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
        New goal
      </button>
    );
  }

  return (
    <form onSubmit={submit} className="card w-full space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">New goal</h2>
        <button type="button" className="text-sm text-gray-400 hover:text-gray-600" onClick={() => setOpen(false)}>
          ✕ Close
        </button>
      </div>
      <div>
        <label className="label" htmlFor="goal-title">Title</label>
        <input
          id="goal-title"
          className="input"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Ship the reporting dashboard"
          required
        />
      </div>
      <div>
        <label className="label" htmlFor="goal-description">Description (optional)</label>
        <textarea
          id="goal-description"
          className="input"
          rows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {employees.length > 0 && (
          <div>
            <label className="label" htmlFor="goal-employee">Employee</label>
            <select
              id="goal-employee"
              className="input"
              value={employeeId}
              onChange={(e) => setEmployeeId(e.target.value)}
            >
              <option value="">Myself</option>
              {employees.map((emp) => (
                <option key={emp.id} value={emp.id}>
                  {emp.name}
                </option>
              ))}
            </select>
          </div>
        )}
        <div>
          <label className="label" htmlFor="goal-type">Type</label>
          <select id="goal-type" className="input" value={type} onChange={(e) => setType(e.target.value)}>
            <option value="individual">Individual</option>
            <option value="team">Team</option>
            <option value="company">Company</option>
          </select>
        </div>
        <div>
          <label className="label" htmlFor="goal-metric">Metric</label>
          <select
            id="goal-metric"
            className="input"
            value={metricType}
            onChange={(e) => {
              setMetricType(e.target.value);
              if (e.target.value === "percentage") setTargetValue("100");
            }}
          >
            <option value="percentage">Percentage</option>
            <option value="number">Number</option>
            <option value="boolean">Done / not done</option>
          </select>
        </div>
        {metricType !== "boolean" && (
          <div>
            <label className="label" htmlFor="goal-target">Target value</label>
            <input
              id="goal-target"
              type="number"
              min="0.01"
              step="any"
              className="input"
              value={targetValue}
              onChange={(e) => setTargetValue(e.target.value)}
              required
            />
          </div>
        )}
        <div>
          <label className="label" htmlFor="goal-due">Due date (optional)</label>
          <input
            id="goal-due"
            type="date"
            className="input"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
          />
        </div>
      </div>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? "Creating…" : "Create goal"}
        </button>
        <button type="button" className="btn-secondary" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
  );
}
