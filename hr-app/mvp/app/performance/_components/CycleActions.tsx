"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function CycleActions({ cycleId, status }: { cycleId: number; status: string }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function act(action: "activate" | "close") {
    setError(null);
    setBusy(true);
    try {
      const res = await fetch(`/api/performance/cycles/${cycleId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Something went wrong.");
        return;
      }
      router.refresh();
    } catch {
      setError("Network error — please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex gap-2">
        {status === "setup" && (
          <button className="btn-primary text-sm" onClick={() => act("activate")} disabled={busy}>
            {busy ? "Working…" : "Activate"}
          </button>
        )}
        {status === "active" && (
          <button className="btn-secondary text-sm" onClick={() => act("close")} disabled={busy}>
            {busy ? "Working…" : "Close"}
          </button>
        )}
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
