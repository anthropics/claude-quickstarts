"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface AddTemplateTaskFormProps {
  templateId: number;
}

export default function AddTemplateTaskForm({ templateId }: AddTemplateTaskFormProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    setError(null);

    const fd = new FormData(e.currentTarget);
    const body = {
      title: fd.get("title") as string,
      description: (fd.get("description") as string) || undefined,
      assignee_type: fd.get("assignee_type") as string,
      due_offset_days: Number(fd.get("due_offset_days") ?? 0),
    };

    try {
      const res = await fetch(`/api/onboarding/templates/${templateId}/tasks`, {
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
        + Add task
      </button>
    );
  }

  return (
    <div className="card mt-4 border-brand-200">
      <h3 className="mb-4 font-semibold">Add Template Task</h3>
      {error && (
        <div className="mb-3 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      )}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="label" htmlFor="task-title">Title *</label>
          <input id="task-title" name="title" required className="input" />
        </div>
        <div>
          <label className="label" htmlFor="task-description">Description</label>
          <textarea id="task-description" name="description" rows={2} className="input" />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="task-assignee-type">Assignee Type *</label>
            <select id="task-assignee-type" name="assignee_type" required className="input" defaultValue="new_hire">
              <option value="new_hire">New Hire</option>
              <option value="hr">HR</option>
              <option value="manager">Manager</option>
              <option value="it">IT</option>
            </select>
          </div>
          <div>
            <label className="label" htmlFor="task-offset">Days from start date *</label>
            <input
              id="task-offset"
              name="due_offset_days"
              type="number"
              required
              className="input"
              defaultValue="0"
              placeholder="0"
            />
          </div>
        </div>
        <div className="flex gap-2 pt-1">
          <button type="submit" disabled={saving} className="btn-primary">
            {saving ? "Adding…" : "Add task"}
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
