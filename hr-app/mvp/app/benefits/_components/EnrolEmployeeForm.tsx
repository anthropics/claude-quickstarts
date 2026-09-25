"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface TierOption {
  id: number;
  name: string;
  monthly_cost_employee: number;
  monthly_cost_employer: number;
}

interface PlanGroup {
  id: number;
  name: string;
  tiers: TierOption[];
}

interface Props {
  employees: { id: number; name: string }[];
  plans: PlanGroup[];
}

export default function EnrolEmployeeForm({ employees, plans }: Props) {
  const router = useRouter();
  const [employeeId, setEmployeeId] = useState("");
  const [tierId, setTierId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await fetch("/api/benefits/elections", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tier_id: Number(tierId), employee_id: Number(employeeId) }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Something went wrong.");
        return;
      }
      setEmployeeId("");
      setTierId("");
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
          <label className="label" htmlFor="en-employee">Employee</label>
          <select
            id="en-employee"
            className="input"
            value={employeeId}
            onChange={(e) => setEmployeeId(e.target.value)}
            required
          >
            <option value="" disabled>Select employee…</option>
            {employees.map((emp) => (
              <option key={emp.id} value={emp.id}>{emp.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="en-tier">Plan &amp; tier</label>
          <select id="en-tier" className="input" value={tierId} onChange={(e) => setTierId(e.target.value)} required>
            <option value="" disabled>Select tier…</option>
            {plans.map((plan) => (
              <optgroup key={plan.id} label={plan.name}>
                {plan.tiers.map((tier) => (
                  <option key={tier.id} value={tier.id}>
                    {tier.name} (employee R{tier.monthly_cost_employee} / employer R{tier.monthly_cost_employer})
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>
      </div>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <p className="text-xs text-gray-500">
        If the employee already has an active election on another tier of the same plan, it will be ended automatically.
      </p>
      <button type="submit" className="btn-primary" disabled={busy}>
        {busy ? "Enrolling…" : "Enrol employee"}
      </button>
    </form>
  );
}
