"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Department {
  id: number;
  name: string;
}

interface EditTemplateFormProps {
  templateId: number;
  initialName: string;
  initialDescription: string | null;
  initialDepartmentId: number | null;
  departments: Department[];
}

export default function EditTemplateForm({
  templateId,
  initialName,
  initialDescription,
  initialDepartmentId,
  departments,
}: EditTemplateFormProps) {
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
      const res = await fetch(`/api/onboarding/templates/${templateId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Failed to update template.");
        return;
      }
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
        Edit details
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-semibold">Edit Template</h2>
        {error && (
          <div className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label" htmlFor="edit-tpl-name">Template name *</label>
            <input
              id="edit-tpl-name"
              name="name"
              required
              className="input"
              defaultValue={initialName}
            />
          </div>
          <div>
            <label className="label" htmlFor="edit-tpl-description">Description</label>
            <textarea
              id="edit-tpl-description"
              name="description"
              rows={3}
              className="input"
              defaultValue={initialDescription ?? ""}
            />
          </div>
          <div>
            <label className="label" htmlFor="edit-tpl-department">Department (optional)</label>
            <select
              id="edit-tpl-department"
              name="department_id"
              className="input"
              defaultValue={initialDepartmentId ?? ""}
            >
              <option value="">All departments</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
          </div>
          <div className="flex gap-2 pt-1">
            <button type="submit" disabled={saving} className="btn-primary">
              {saving ? "Saving…" : "Save changes"}
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
