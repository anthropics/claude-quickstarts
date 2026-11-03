"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function EnrolButton({ tierId, switching }: { tierId: number; switching?: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function enrol() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/benefits/elections", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tier_id: tierId }),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.error ?? "Failed to enrol.");
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
        className="rounded-lg border border-brand-600 px-2.5 py-1 text-xs font-medium text-brand-600 hover:bg-brand-100 disabled:opacity-50"
        onClick={enrol}
        disabled={busy}
      >
        {busy ? "Enrolling…" : switching ? "Switch to this tier" : "Enrol"}
      </button>
      {error && <span className="text-xs text-red-600">{error}</span>}
    </span>
  );
}
