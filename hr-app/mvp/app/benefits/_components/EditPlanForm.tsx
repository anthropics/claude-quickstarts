"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { BENEFIT_CATEGORIES, categoryLabel } from "../_lib/benefits";

interface Props {
  planId: number;
  initialName: string;
  initialCategory: string;
  initialProvider: string | null;
  initialDescription: string | null;
}

export default function EditPlanForm({ planId, initialName, initialCategory, initialProvider, initialDescription }: Props) {
  const router = useRouter();
  const [name, setName] = useState(initialName);
  const [category, setCategory] = useState(initialCategory);
  const [provider, setProvider] = useState(initialProvider ?? "");
  const [description, setDescription] = useState(initialDescription ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    setBusy(true);
    try {
      const res = await fetch(`/api/benefits/plans/${planId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, category, provider, description }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Something went wrong.");
        return;
      }
      setSaved(true);
      router.refresh();
    } catch {
      setError("Network error — please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="label" htmlFor="ep-name">Name</label>
          <input id="ep-name" className="input" value={name} onChange={(e) => setName(e.target.value)} required />
        </div>
        <div>
          <label className="label" htmlFor="ep-category">Category</label>
          <select id="ep-category" className="input" value={category} onChange={(e) => setCategory(e.target.value)}>
            {BENEFIT_CATEGORIES.map((c) => (
              <option key={c} value={c}>{categoryLabel(c)}</option>
            ))}
          </select>
        </div>
      </div>
      <div>
        <label className="label" htmlFor="ep-provider">Provider</label>
        <input id="ep-provider" className="input" value={provider} onChange={(e) => setProvider(e.target.value)} />
      </div>
      <div>
        <label className="label" htmlFor="ep-description">Description</label>
        <textarea
          id="ep-description"
          className="input"
          rows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <div className="flex items-center gap-3">
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? "Saving…" : "Save changes"}
        </button>
        {saved && <span className="text-sm text-green-700">Saved.</span>}
      </div>
    </form>
  );
}
