"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Department {
  id: number;
  name: string;
}

interface NewTemplateFormProps {
  departments: Department[];
}

export default function NewTemplateForm({ departments }: NewTemplateFormProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    setError(null);

    const fd = new FormData(e.currentTarget);
    const deptRaw = fd.get("department_id") as string;
    const body = {
      name: fd.get("name") as string,
      description: (fd.get("description") as string) || undefined,
      department_id: deptRaw ? Number(deptRaw) : null,
    };

    try {
      const res = await fetch("/api/onboarding/templates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Failed to create template.");
        return;
      }
      router.push(`/onboarding/templates/${data.id}`);
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <button className="btn-primary text-sm" onClick={() => setOpen(true)}>
        + New template
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-semibold">New Onboarding Template</h2>
        {error && (
          <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label" htmlFor="tpl-name">Template name *</label>
            <input id="tpl-name" name="name" required className="input" placeholder="e.g. Engineering Onboarding" />
          </div>
          <div>
            <label className="label" htmlFor="tpl-description">Description</label>
            <textarea id="tpl-description" name="description" rows={3} className="input" placeholder="Brief description…" />
          </div>
          <div>
            <label className="label" htmlFor="tpl-department">Department (optional)</label>
            <select id="tpl-department" name="department_id" className="input" defaultValue="">
              <option value="">All departments</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
          </div>
          <div className="flex gap-2 pt-1">
            <button type="submit" disabled={saving} className="btn-primary">
              {saving ? "Creating…" : "Create template"}
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
