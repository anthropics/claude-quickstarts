"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Employee {
  id: number;
  name: string;
}

interface ScheduleInterviewFormProps {
  appId: number;
  employees: Employee[];
}

export default function ScheduleInterviewForm({ appId, employees }: ScheduleInterviewFormProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedInterviewers, setSelectedInterviewers] = useState<number[]>([]);

  function toggleInterviewer(id: number) {
    setSelectedInterviewers((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    setError(null);

    const form = e.currentTarget;
    const data = new FormData(form);

    const payload = {
      scheduled_at: `${data.get("date") as string}T${data.get("time") as string}`,
      duration_minutes: Number(data.get("duration_minutes")),
      format: data.get("format") as string,
      interviewer_ids: selectedInterviewers,
      notes: data.get("notes") as string || null,
    };

    try {
      const res = await fetch(`/api/recruitment/applications/${appId}/interviews`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (!res.ok) {
        setError(json.error ?? "Failed to schedule interview.");
        setSaving(false);
        return;
      }
      setOpen(false);
      setSelectedInterviewers([]);
      form.reset();
      router.refresh();
    } catch {
      setError("Network error.");
    }
    setSaving(false);
  }

  return (
    <div className="mt-3">
      {!open ? (
        <button onClick={() => setOpen(true)} className="btn-secondary text-sm">
          Schedule interview
        </button>
      ) : (
        <div className="mt-3 rounded-lg border border-gray-200 bg-gray-50 p-4">
          <h4 className="mb-3 font-medium">Schedule interview</h4>
          {error && (
            <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="label">Date *</label>
                <input name="date" type="date" required className="input" />
              </div>
              <div>
                <label className="label">Time *</label>
                <input name="time" type="time" required className="input" defaultValue="10:00" />
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="label">Duration (minutes)</label>
                <input name="duration_minutes" type="number" min={15} max={480} defaultValue={60} className="input" />
              </div>
              <div>
                <label className="label">Format</label>
                <select name="format" className="input" defaultValue="video">
                  <option value="video">Video call</option>
                  <option value="in_person">In person</option>
                  <option value="phone">Phone</option>
                </select>
              </div>
            </div>
            <div>
              <label className="label">Interviewers</label>
              <div className="mt-1 max-h-36 overflow-y-auto rounded-lg border border-gray-200 bg-white p-2 space-y-1">
                {employees.map((emp) => (
                  <label key={emp.id} className="flex items-center gap-2 cursor-pointer text-sm hover:bg-gray-50 rounded px-1 py-0.5">
                    <input
                      type="checkbox"
                      checked={selectedInterviewers.includes(emp.id)}
                      onChange={() => toggleInterviewer(emp.id)}
                      className="rounded"
                    />
                    {emp.name}
                  </label>
                ))}
              </div>
            </div>
            <div>
              <label className="label">Notes</label>
              <textarea name="notes" rows={2} className="input resize-y" />
            </div>
            <div className="flex gap-2">
              <button type="submit" disabled={saving} className="btn-primary text-sm">
                {saving ? "Scheduling…" : "Schedule"}
              </button>
              <button
                type="button"
                onClick={() => { setOpen(false); setError(null); setSelectedInterviewers([]); }}
                className="btn-secondary text-sm"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
