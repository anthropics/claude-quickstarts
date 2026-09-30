"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Employee {
  id: number;
  first_name: string;
  last_name: string;
}

interface AdHocTaskFormProps {
  instanceId: number;
  employees: Employee[];
}

export default function AdHocTaskForm({ instanceId, employees }: AdHocTaskFormProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    setError(null);

    const fd = new FormData(e.currentTarget);
    const assignedToRaw = fd.get("assigned_to_id") as string;
    const body = {
      title: fd.get("title") as string,
      description: (fd.get("description") as string) || undefined,
      assignee_type: fd.get("assignee_type") as string,
      assigned_to_id: assignedToRaw ? Number(assignedToRaw) : null,
      due_date: (fd.get("due_date") as string) || undefined,
    };

    try {
      const res = await fetch(`/api/onboarding/instances/${instanceId}/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Failed to add task.");
        return;
      }
      (e.target as HTMLFormElement).reset();
      setOpen(false);
      router.refresh();
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <button className="btn-secondary text-sm" onClick={() => setOpen(true)}>
        + Add ad-hoc task
      </button>
    );
  }

  return (
    <div className="card border-brand-200 mt-4">
      <h3 className="mb-4 font-semibold">Add Ad-hoc Task</h3>
      {error && (
        <div className="mb-3 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      )}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="label" htmlFor="adhoc-title">Title *</label>
          <input id="adhoc-title" name="title" required className="input" />
        </div>
        <div>
          <label className="label" htmlFor="adhoc-description">Description</label>
          <textarea id="adhoc-description" name="description" rows={2} className="input" />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="adhoc-assignee-type">Assignee Type *</label>
            <select id="adhoc-assignee-type" name="assignee_type" required className="input" defaultValue="new_hire">
              <option value="new_hire">New Hire</option>
              <option value="hr">HR</option>
              <option value="manager">Manager</option>
              <option value="it">IT</option>
            </select>
          </div>
          <div>
            <label className="label" htmlFor="adhoc-assigned-to">Assign To</label>
            <select id="adhoc-assigned-to" name="assigned_to_id" className="input" defaultValue="">
              <option value="">— none —</option>
              {employees.map((emp) => (
                <option key={emp.id} value={emp.id}>
                  {emp.first_name} {emp.last_name}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div>
          <label className="label" htmlFor="adhoc-due-date">Due Date</label>
          <input id="adhoc-due-date" name="due_date" type="date" className="input" />
        </div>
        <div className="flex gap-2 pt-1">
          <button type="submit" disabled={saving} className="btn-primary">
            {saving ? "Saving…" : "Add task"}
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={() => { setOpen(false); setError(null); }}
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
