"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function ReimburseButton({ claimId }: { claimId: number }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function reimburse() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/expenses/claims/${claimId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "reimburse" }),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.error ?? "Failed to mark reimbursed.");
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
      <button className="btn-secondary px-2.5 py-1 text-xs" onClick={reimburse} disabled={busy}>
        {busy ? "Marking…" : "Mark reimbursed"}
      </button>
      {error && <span className="text-xs text-red-600">{error}</span>}
    </span>
  );
}
