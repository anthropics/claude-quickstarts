"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { MERGE_FIELDS } from "../_lib/render";

const TYPES = [
  { value: "appointment", label: "Appointment" },
  { value: "confirmation", label: "Confirmation" },
  { value: "warning", label: "Warning" },
  { value: "increase", label: "Increase" },
  { value: "general", label: "General" },
];

interface Props {
  /** When provided the form edits this template, otherwise it creates a new one. */
  template?: { id: number; name: string; type: string; body_template: string };
}

export default function TemplateForm({ template }: Props) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const isEdit = !!template;

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSaving(true);

    const fd = new FormData(e.currentTarget);
    const payload = {
      name: ((fd.get("name") as string | null) ?? "").trim(),
      type: (fd.get("type") as string | null) ?? "general",
      body_template: (fd.get("body_template") as string | null) ?? "",
    };

    try {
      const res = await fetch(isEdit ? `/api/letters/templates/${template.id}` : "/api/letters/templates", {
        method: isEdit ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = (await res.json()) as { id?: number; error?: string };
      if (!res.ok) {
        setError(data.error ?? "Something went wrong.");
        setSaving(false);
        return;
      }
      router.push("/letters");
      router.refresh();
    } catch {
      setError("Network error — please try again.");
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      <div className="card">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="name">Name *</label>
            <input id="name" name="name" className="input" required defaultValue={template?.name} />
          </div>
          <div>
            <label className="label" htmlFor="type">Type *</label>
            <select id="type" name="type" className="input" defaultValue={template?.type ?? "general"}>
              {TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <div className="sm:col-span-2">
            <label className="label" htmlFor="body_template">Body *</label>
            <textarea
              id="body_template"
              name="body_template"
              className="input font-mono"
              rows={14}
              required
              defaultValue={template?.body_template}
            />
            <p className="mt-2 text-xs text-gray-500">
              Available merge fields:{" "}
              {MERGE_FIELDS.map((f, i) => (
                <span key={f}>
                  {i > 0 && ", "}
                  <code className="rounded bg-gray-100 px-1 py-0.5">{`{{${f}}}`}</code>
                </span>
              ))}
            </p>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? "Saving…" : isEdit ? "Save changes" : "Create template"}
        </button>
        <Link href="/letters" className="btn-secondary">
          Cancel
        </Link>
      </div>
    </form>
  );
}
