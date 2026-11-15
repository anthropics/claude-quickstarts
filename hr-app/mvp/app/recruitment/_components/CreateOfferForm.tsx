"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface CreateOfferFormProps {
  appId: number;
}

export default function CreateOfferForm({ appId }: CreateOfferFormProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    setError(null);

    const form = e.currentTarget;
    const data = new FormData(form);

    const payload = {
      salary: Number(data.get("salary")),
      start_date: data.get("start_date") as string,
      expiry_date: data.get("expiry_date") as string,
      notes: data.get("notes") as string || null,
    };

    try {
      const res = await fetch(`/api/recruitment/applications/${appId}/offer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (!res.ok) {
        setError(json.error ?? "Failed to create offer.");
        setSaving(false);
        return;
      }
      setOpen(false);
      router.refresh();
    } catch {
      setError("Network error.");
    }
    setSaving(false);
  }

  return (
    <div className="mt-3">
      {!open ? (
        <button onClick={() => setOpen(true)} className="btn-primary text-sm">
          Create offer
        </button>
      ) : (
        <div className="mt-3 rounded-lg border border-gray-200 bg-gray-50 p-4">
          <h4 className="mb-3 font-medium">Create offer</h4>
          {error && (
            <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="label">Monthly salary (ZAR) *</label>
              <input name="salary" type="number" required min={1} step="0.01" className="input" placeholder="e.g. 75000" />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="label">Start date *</label>
                <input name="start_date" type="date" required className="input" />
              </div>
              <div>
                <label className="label">Offer expiry *</label>
                <input name="expiry_date" type="date" required className="input" />
              </div>
            </div>
            <div>
              <label className="label">Notes</label>
              <textarea name="notes" rows={3} className="input resize-y" placeholder="e.g. Includes 20% bonus on target earnings" />
            </div>
            <div className="flex gap-2">
              <button type="submit" disabled={saving} className="btn-primary text-sm">
                {saving ? "Creating…" : "Create offer"}
              </button>
              <button
                type="button"
                onClick={() => { setOpen(false); setError(null); }}
                className="btn-secondary text-sm"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
