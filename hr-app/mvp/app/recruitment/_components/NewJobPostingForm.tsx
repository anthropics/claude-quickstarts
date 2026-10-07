"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Department {
  id: number;
  name: string;
}

interface NewJobPostingFormProps {
  departments: Department[];
}

export default function NewJobPostingForm({ departments }: NewJobPostingFormProps) {
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
      const res = await fetch("/api/recruitment/postings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (!res.ok) {
        setError(json.error ?? "Failed to create posting.");
        setSaving(false);
        return;
      }
      router.push(`/recruitment/${json.id}`);
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
        <input name="title" required className="input" placeholder="e.g. Senior Software Engineer" />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="label">Department</label>
          <select name="department_id" className="input">
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
          <input name="location" className="input" placeholder="e.g. Cape Town / Remote" />
        </div>
      </div>

      <div>
        <label className="label">Employment type</label>
        <select name="employment_type" className="input" defaultValue="full_time">
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
          placeholder="Describe the role, responsibilities, and team..."
        />
      </div>

      <div>
        <label className="label">Requirements</label>
        <textarea
          name="requirements"
          rows={4}
          className="input resize-y"
          placeholder="List required skills, qualifications, and experience..."
        />
      </div>

      <div>
        <label className="label">Closes at (optional)</label>
        <input name="closes_at" type="date" className="input" />
      </div>

      <div className="flex gap-3 pt-2">
        <button type="submit" disabled={saving} className="btn-primary">
          {saving ? "Saving…" : "Save as draft"}
        </button>
        <a href="/recruitment" className="btn-secondary">
          Cancel
        </a>
      </div>
    </form>
  );
}
