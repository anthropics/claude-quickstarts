"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function ClaimDecisionButtons({ claimId }: { claimId: number }) {
  const router = useRouter();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function decide(action: "approve" | "reject") {
    setBusy(action);
    setError(null);
    try {
      const res = await fetch(`/api/expenses/claims/${claimId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, note: note || undefined }),
      });
      if (!res.ok) {
        const data = await res.json();
        setError(data.error ?? "Failed to update claim.");
        return;
      }
      router.refresh();
    } catch {
      setError("Network error.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-2">
      <input
        className="input"
        placeholder="Optional note…"
        value={note}
        onChange={(e) => setNote(e.target.value)}
      />
      <div className="flex gap-2">
        <button className="btn-primary" onClick={() => decide("approve")} disabled={busy !== null}>
          {busy === "approve" ? "Approving…" : "Approve"}
        </button>
        <button className="btn-danger" onClick={() => decide("reject")} disabled={busy !== null}>
          {busy === "reject" ? "Rejecting…" : "Reject"}
        </button>
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
