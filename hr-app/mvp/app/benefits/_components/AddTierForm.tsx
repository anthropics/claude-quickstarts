"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function AddTierForm({ planId }: { planId: number }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [costEmployee, setCostEmployee] = useState("0");
  const [costEmployer, setCostEmployer] = useState("0");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await fetch(`/api/benefits/plans/${planId}/tiers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          monthly_cost_employee: Number(costEmployee),
          monthly_cost_employer: Number(costEmployer),
          description,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Something went wrong.");
        return;
      }
      setName("");
      setCostEmployee("0");
      setCostEmployer("0");
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
      <div className="grid gap-4 sm:grid-cols-3">
        <div>
          <label className="label" htmlFor="bt-name">Tier name</label>
          <input
            id="bt-name"
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder="e.g. Classic"
          />
        </div>
        <div>
          <label className="label" htmlFor="bt-emp">Employee cost (R/month)</label>
          <input
            id="bt-emp"
            type="number"
            min="0"
            step="0.01"
            className="input"
            value={costEmployee}
            onChange={(e) => setCostEmployee(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="bt-er">Employer cost (R/month)</label>
          <input
            id="bt-er"
            type="number"
            min="0"
            step="0.01"
            className="input"
            value={costEmployer}
            onChange={(e) => setCostEmployer(e.target.value)}
            required
          />
        </div>
      </div>
      <div>
        <label className="label" htmlFor="bt-description">Description</label>
        <input
          id="bt-description"
          className="input"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="e.g. Hospital + day-to-day benefits"
        />
      </div>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <button type="submit" className="btn-secondary" disabled={busy}>
        {busy ? "Adding…" : "Add tier"}
      </button>
    </form>
  );
}
