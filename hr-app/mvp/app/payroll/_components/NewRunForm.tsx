"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function NewRunForm() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const fd = new FormData(e.currentTarget);
    const body = {
      period_start: fd.get("period_start") as string,
      period_end: fd.get("period_end") as string,
      payment_date: fd.get("payment_date") as string,
      notes: (fd.get("notes") as string) || undefined,
    };
    try {
      const res = await fetch("/api/payroll/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Failed to create pay run.");
        return;
      }
      router.push(`/payroll/${data.id}`);
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="card max-w-lg space-y-4">
      <div>
        <label className="label" htmlFor="period_start">
          Period Start
        </label>
        <input id="period_start" name="period_start" type="date" required className="input" />
      </div>
      <div>
        <label className="label" htmlFor="period_end">
          Period End
        </label>
        <input id="period_end" name="period_end" type="date" required className="input" />
      </div>
      <div>
        <label className="label" htmlFor="payment_date">
          Payment Date
        </label>
        <input id="payment_date" name="payment_date" type="date" required className="input" />
      </div>
      <div>
        <label className="label" htmlFor="notes">
          Notes (optional)
        </label>
        <textarea id="notes" name="notes" rows={3} className="input" placeholder="Any notes about this pay run…" />
      </div>
      {error && (
        <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      )}
      <div className="flex gap-3">
        <button type="submit" disabled={loading} className="btn-primary">
          {loading ? "Calculating…" : "Create Pay Run"}
        </button>
        <a href="/payroll" className="btn-secondary">
          Cancel
        </a>
      </div>
    </form>
  );
}
