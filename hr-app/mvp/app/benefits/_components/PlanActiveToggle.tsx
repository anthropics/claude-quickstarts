"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function PlanActiveToggle({ planId, active }: { planId: number; active: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/benefits/plans/${planId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active: !active }),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.error ?? "Failed to update plan.");
        return;
      }
      router.refresh();
    } catch {
      setError("Network error.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex items-center gap-2">
      <button
        className={`rounded-lg border px-2.5 py-1 text-xs font-medium disabled:opacity-50 ${
          active
            ? "border-red-200 text-red-600 hover:bg-red-50"
            : "border-green-200 text-green-700 hover:bg-green-50"
        }`}
        onClick={toggle}
        disabled={busy}
      >
        {busy ? "Updating…" : active ? "Deactivate" : "Activate"}
      </button>
      {error && <span className="text-xs text-red-600">{error}</span>}
    </span>
  );
}
