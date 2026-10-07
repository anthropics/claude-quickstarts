"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function NewCycleForm() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState("biannual");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [launch, setLaunch] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await fetch("/api/performance/cycles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          type,
          period_start: periodStart,
          period_end: periodEnd,
          launch,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Something went wrong.");
        return;
      }
      setOpen(false);
      setName("");
      setPeriodStart("");
      setPeriodEnd("");
      router.refresh();
    } catch {
      setError("Network error — please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button className="btn-primary" onClick={() => setOpen(true)}>
        New cycle
      </button>
    );
  }

  return (
    <form onSubmit={submit} className="card w-full space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">New review cycle</h2>
        <button type="button" className="text-sm text-gray-400 hover:text-gray-600" onClick={() => setOpen(false)}>
          ✕ Close
        </button>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <label className="label" htmlFor="cy-name">Name</label>
          <input
            id="cy-name"
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. H2 2026 Performance Review"
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="cy-type">Type</label>
          <select id="cy-type" className="input" value={type} onChange={(e) => setType(e.target.value)}>
            <option value="annual">Annual</option>
            <option value="biannual">Biannual</option>
            <option value="quarterly">Quarterly</option>
            <option value="probation">Probation</option>
          </select>
        </div>
        <div>
          <label className="label" htmlFor="cy-start">Period start</label>
          <input
            id="cy-start"
            type="date"
            className="input"
            value={periodStart}
            onChange={(e) => setPeriodStart(e.target.value)}
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="cy-end">Period end</label>
          <input
            id="cy-end"
            type="date"
            className="input"
            value={periodEnd}
            onChange={(e) => setPeriodEnd(e.target.value)}
            required
          />
        </div>
      </div>
      <label className="flex items-center gap-2 text-sm text-gray-700">
        <input type="checkbox" checked={launch} onChange={(e) => setLaunch(e.target.checked)} />
        Launch now — generate self + manager review pairs for every active employee with a manager
      </label>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? "Creating…" : launch ? "Create & launch" : "Create cycle"}
        </button>
        <button type="button" className="btn-secondary" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
  );
}
