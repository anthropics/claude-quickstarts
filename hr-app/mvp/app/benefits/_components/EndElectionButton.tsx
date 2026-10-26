"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function EndElectionButton({ electionId, label }: { electionId: number; label?: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function end() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/benefits/elections/${electionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "end" }),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.error ?? "Failed to end enrolment.");
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
        className="rounded-lg border border-red-200 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
        onClick={end}
        disabled={busy}
      >
        {busy ? "Ending…" : label ?? "End enrolment"}
      </button>
      {error && <span className="text-xs text-red-600">{error}</span>}
    </span>
  );
}
