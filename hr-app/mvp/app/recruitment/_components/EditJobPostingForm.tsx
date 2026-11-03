"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Department {
  id: number;
  name: string;
}

interface Posting {
  id: number;
  title: string;
  department_id: number | null;
  location: string | null;
  employment_type: string;
  description: string | null;
  requirements: string | null;
  closes_at: string | null;
}

interface EditJobPostingFormProps {
  posting: Posting;
  departments: Department[];
}

export default function EditJobPostingForm({ posting, departments }: EditJobPostingFormProps) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSaving(true);

    const form = e.currentTarget;
    const data = new FormData(form);

    const payload = {
      title: data.get("title") as string,
      department_id: data.get("department_id") ? Number(data.get("department_id")) : null,
      location: data.get("location") as string,
      employment_type: data.get("employment_type") as string,
      description: data.get("description") as string,
      requirements: data.get("requirements") as string,
      closes_at: (data.get("closes_at") as string) || null,
    };

    try {
      const res = await fetch(`/api/recruitment/postings/${posting.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (!res.ok) {
        setError(json.error ?? "Failed to update posting.");
        setSaving(false);
        return;
      }
      router.push(`/recruitment/${posting.id}`);
    } catch {
      setError("Network error. Please try again.");
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5 max-w-2xl">
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div>
        <label className="label">Job title *</label>
        <input name="title" required className="input" defaultValue={posting.title} />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="label">Department</label>
          <select name="department_id" className="input" defaultValue={posting.department_id ?? ""}>
            <option value="">— Select department —</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Location</label>
          <input name="location" className="input" defaultValue={posting.location ?? ""} />
        </div>
      </div>

      <div>
        <label className="label">Employment type</label>
        <select name="employment_type" className="input" defaultValue={posting.employment_type}>
          <option value="full_time">Full-time</option>
          <option value="part_time">Part-time</option>
          <option value="contract">Contract</option>
          <option value="intern">Intern</option>
        </select>
      </div>

      <div>
        <label className="label">Description</label>
        <textarea
          name="description"
          rows={5}
          className="input resize-y"
          defaultValue={posting.description ?? ""}
        />
      </div>

      <div>
        <label className="label">Requirements</label>
        <textarea
          name="requirements"
          rows={4}
          className="input resize-y"
          defaultValue={posting.requirements ?? ""}
        />
      </div>

      <div>
        <label className="label">Closes at (optional)</label>
        <input
          name="closes_at"
          type="date"
          className="input"
          defaultValue={posting.closes_at ?? ""}
        />
      </div>

      <div className="flex gap-3 pt-2">
        <button type="submit" disabled={saving} className="btn-primary">
          {saving ? "Saving…" : "Save changes"}
        </button>
        <a href={`/recruitment/${posting.id}`} className="btn-secondary">
          Cancel
        </a>
      </div>
    </form>
  );
}
