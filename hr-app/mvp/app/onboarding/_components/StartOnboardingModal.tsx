"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Employee {
  id: number;
  first_name: string;
  last_name: string;
}

interface Template {
  id: number;
  name: string;
}

interface StartOnboardingModalProps {
  employees: Employee[];
  templates: Template[];
}

export default function StartOnboardingModal({ employees, templates }: StartOnboardingModalProps) {
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
      employee_id: Number(fd.get("employee_id")),
      template_id: Number(fd.get("template_id")),
    };

    try {
      const res = await fetch("/api/onboarding/instances", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Failed to start onboarding.");
        return;
      }
      router.push(`/onboarding/${data.id}`);
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <button className="btn-primary text-sm" onClick={() => setOpen(true)}>
        + Start onboarding
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-semibold">Start Onboarding</h2>
        {error && (
          <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label" htmlFor="start-employee">Employee *</label>
            <select id="start-employee" name="employee_id" required className="input" defaultValue="">
              <option value="" disabled>Select employee…</option>
              {employees.map((emp) => (
                <option key={emp.id} value={emp.id}>
                  {emp.first_name} {emp.last_name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="start-template">Onboarding Template *</label>
            <select id="start-template" name="template_id" required className="input" defaultValue="">
              <option value="" disabled>Select template…</option>
              {templates.map((tpl) => (
                <option key={tpl.id} value={tpl.id}>
                  {tpl.name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex gap-2 pt-1">
            <button type="submit" disabled={saving} className="btn-primary">
              {saving ? "Starting…" : "Start onboarding"}
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
    </div>
  );
}
