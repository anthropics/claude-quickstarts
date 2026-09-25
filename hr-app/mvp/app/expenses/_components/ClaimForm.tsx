"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { formatRand } from "../_lib/format";

export interface CategoryOption {
  id: number;
  name: string;
  code: string;
  monthly_limit: number | null;
  requires_receipt: number;
}

export default function ClaimForm({ categories }: { categories: CategoryOption[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [categoryId, setCategoryId] = useState(categories[0]?.id ?? 0);
  const [amount, setAmount] = useState("");
  const [expenseDate, setExpenseDate] = useState("");
  const [description, setDescription] = useState("");
  const [receipt, setReceipt] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const category = categories.find((c) => c.id === categoryId);
  const receiptRequired = category?.requires_receipt === 1;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await fetch("/api/expenses/claims", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          category_id: categoryId,
          amount: Number(amount),
          expense_date: expenseDate,
          description,
          receipt_filename: receipt || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Something went wrong.");
        return;
      }
      setOpen(false);
      setAmount("");
      setExpenseDate("");
      setDescription("");
      setReceipt("");
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
        New claim
      </button>
    );
  }

  return (
    <form onSubmit={submit} className="card w-full space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">New expense claim</h2>
        <button type="button" className="text-sm text-gray-400 hover:text-gray-600" onClick={() => setOpen(false)}>
          ✕ Close
        </button>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <div>
          <label className="label" htmlFor="ec-category">Category</label>
          <select
            id="ec-category"
            className="input"
            value={categoryId}
            onChange={(e) => setCategoryId(Number(e.target.value))}
          >
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          {category && (
            <p className="mt-1 text-xs text-gray-500">
              {category.monthly_limit !== null
                ? `Monthly limit: ${formatRand(category.monthly_limit)}`
                : "No monthly limit"}
              {" · "}
              {receiptRequired ? "Receipt required" : "No receipt needed"}
            </p>
          )}
        </div>
        <div>
          <label className="label" htmlFor="ec-amount">Amount (R)</label>
          <input
            id="ec-amount"
            type="number"
            step="0.01"
            min="0.01"
            className="input"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="e.g. 1240.50"
            required
          />
        </div>
        <div>
          <label className="label" htmlFor="ec-date">Expense date</label>
          <input
            id="ec-date"
            type="date"
            className="input"
            value={expenseDate}
            onChange={(e) => setExpenseDate(e.target.value)}
            required
          />
        </div>
      </div>
      <div>
        <label className="label" htmlFor="ec-description">Description</label>
        <input
          id="ec-description"
          className="input"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="e.g. Client visit — JHB to PTA return mileage"
          required
        />
      </div>
      <div>
        <label className="label" htmlFor="ec-receipt">
          Receipt filename {receiptRequired ? "(required)" : "(optional)"}
        </label>
        <input
          id="ec-receipt"
          className="input"
          value={receipt}
          onChange={(e) => setReceipt(e.target.value)}
          placeholder="e.g. receipt_uber_jul4.pdf"
          required={receiptRequired}
        />
        <p className="mt-1 text-xs text-gray-400">
          MVP: enter the filename of your receipt — file uploads arrive post-MVP.
        </p>
      </div>
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" className="btn-primary" disabled={busy}>
          {busy ? "Submitting…" : "Submit claim"}
        </button>
        <button type="button" className="btn-secondary" onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
  );
}
