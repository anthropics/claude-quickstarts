"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function TimeEntryActions({ entryId }: { entryId: number }) {
  const router = useRouter();
  const [pending, setPending] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function decide(action: "approve" | "reject") {
    setPending(action);
    setError(null);
    try {
      const res = await fetch(`/api/time/entries/${entryId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      if (!res.ok) {
        const data = (await res.json().catch(() => null)) as { error?: string } | null;
        setError(data?.error ?? "Something went wrong.");
      }
      router.refresh();
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <div className="flex gap-2">
        <button className="btn-primary" disabled={pending !== null} onClick={() => decide("approve")}>
          {pending === "approve" ? "Saving…" : "Approve"}
        </button>
        <button className="btn-danger" disabled={pending !== null} onClick={() => decide("reject")}>
          {pending === "reject" ? "Saving…" : "Reject"}
        </button>
      </div>
      {error && <p className="text-xs text-red-600">{error}</p>}
    </div>
  );
}
