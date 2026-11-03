"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function CategoryForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [monthlyLimit, setMonthlyLimit] = useState("");
  const [requiresReceipt, setRequiresReceipt] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await fetch("/api/expenses/categories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          code,
          monthly_limit: monthlyLimit === "" ? null : Number(monthlyLimit),
          requires_receipt: requiresReceipt,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Something went wrong.");
        return;
      }
      setName("");
      setCode("");
      setMonthlyLimit("");
      setRequiresReceipt(true);
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
          <label className="label" htmlFor="cat-name">Name</label>
          <input
            id="cat-name"
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Office Supplies"
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="cat-code">Code</label>
          <input
            id="cat-code"
            className="input font-mono uppercase"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="e.g. SUPPLIES"
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="cat-limit">Monthly limit (R, optional)</label>
          <input
            id="cat-limit"
            type="number"
            step="0.01"
            min="0.01"
            className="input"
            value={monthlyLimit}
            onChange={(e) => setMonthlyLimit(e.target.value)}
            placeholder="Leave blank for no limit"
          />
        </div>
      </div>
      <label className="flex items-center gap-2 text-sm text-gray-700">
        <input
          type="checkbox"
          className="h-4 w-4 rounded border-gray-300"
          checked={requiresReceipt}
          onChange={(e) => setRequiresReceipt(e.target.checked)}
        />
        Receipt required
      </label>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <button type="submit" className="btn-primary" disabled={busy}>
        {busy ? "Adding…" : "Add category"}
      </button>
    </form>
  );
}
