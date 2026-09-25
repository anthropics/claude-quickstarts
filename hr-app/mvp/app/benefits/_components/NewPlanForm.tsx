"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { BENEFIT_CATEGORIES, categoryLabel } from "../_lib/benefits";

export default function NewPlanForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [category, setCategory] = useState("medical");
  const [provider, setProvider] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await fetch("/api/benefits/plans", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, category, provider, description }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Something went wrong.");
        return;
      }
      setName("");
      setCategory("medical");
      setProvider("");
      setDescription("");
      router.refresh();
    } catch {
      setError("Network error — please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <label className="label" htmlFor="bp-name">Name</label>
          <input
            id="bp-name"
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder="e.g. Dental Cover"
          />
        </div>
        <div>
          <label className="label" htmlFor="bp-category">Category</label>
          <select id="bp-category" className="input" value={category} onChange={(e) => setCategory(e.target.value)}>
            {BENEFIT_CATEGORIES.map((c) => (
              <option key={c} value={c}>{categoryLabel(c)}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="bp-provider">Provider</label>
          <input
            id="bp-provider"
            className="input"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            placeholder="e.g. Discovery Health"
          />
        </div>
      </div>
      <div>
        <label className="label" htmlFor="bp-description">Description</label>
        <textarea
          id="bp-description"
          className="input"
          rows={2}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What does this plan cover?"
        />
      </div>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <button type="submit" className="btn-primary" disabled={busy}>
        {busy ? "Creating…" : "Create plan"}
      </button>
    </form>
  );
}
