"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function LeaveTypeForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [colour, setColour] = useState("#3b5bdb");
  const [entitlement, setEntitlement] = useState("0");
  const [paid, setPaid] = useState(true);
  const [probationRestricted, setProbationRestricted] = useState(false);
  const [negativeAllowed, setNegativeAllowed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await fetch("/api/leave/types", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          code,
          colour,
          annual_entitlement_days: Number(entitlement),
          paid,
          probation_restricted: probationRestricted,
          negative_balance_allowed: negativeAllowed,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Something went wrong.");
        return;
      }
      setName("");
      setCode("");
      setEntitlement("0");
      setPaid(true);
      setProbationRestricted(false);
      setNegativeAllowed(false);
      router.refresh();
    } catch {
      setError("Network error — please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <label className="label" htmlFor="lt-name">Name</label>
          <input id="lt-name" className="input" value={name} onChange={(e) => setName(e.target.value)} required placeholder="e.g. Compassionate Leave" />
        </div>
        <div>
          <label className="label" htmlFor="lt-code">Code</label>
          <input id="lt-code" className="input uppercase" value={code} onChange={(e) => setCode(e.target.value)} required placeholder="e.g. COMPASSION" />
        </div>
        <div>
          <label className="label" htmlFor="lt-days">Entitlement (days/year)</label>
          <input id="lt-days" type="number" min="0" step="0.5" className="input" value={entitlement} onChange={(e) => setEntitlement(e.target.value)} required />
        </div>
        <div>
          <label className="label" htmlFor="lt-colour">Colour</label>
          <input id="lt-colour" type="color" className="input h-[38px] p-1" value={colour} onChange={(e) => setColour(e.target.value)} />
        </div>
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-gray-700">
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={paid} onChange={(e) => setPaid(e.target.checked)} />
          Paid
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={probationRestricted} onChange={(e) => setProbationRestricted(e.target.checked)} />
          Restricted during probation
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={negativeAllowed} onChange={(e) => setNegativeAllowed(e.target.checked)} />
          Negative balance allowed
        </label>
      </div>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <button type="submit" className="btn-primary" disabled={busy}>
        {busy ? "Adding…" : "Add leave type"}
      </button>
    </form>
  );
}
