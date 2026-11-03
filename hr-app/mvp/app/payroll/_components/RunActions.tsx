"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Props {
  runId: number;
  status: string;
}

export default function RunActions({ runId, status }: Props) {
  const router = useRouter();
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function doAction(action: string) {
    setLoading(action);
    setError(null);
    try {
      const res = await fetch(`/api/payroll/runs/${runId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Action failed.");
        return;
      }
      router.refresh();
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      {status === "draft" && (
        <button
          onClick={() => doAction("approve")}
          disabled={!!loading}
          className="btn-primary"
        >
          {loading === "approve" ? "Approving…" : "Approve"}
        </button>
      )}
      {status === "approved" && (
        <button
          onClick={() => doAction("mark_paid")}
          disabled={!!loading}
          className="btn-primary"
        >
          {loading === "mark_paid" ? "Updating…" : "Mark as Paid"}
        </button>
      )}
      {(status === "draft" || status === "approved") && (
        <button
          onClick={() => {
            if (confirm("Are you sure you want to cancel this pay run?")) doAction("cancel");
          }}
          disabled={!!loading}
          className="btn-danger"
        >
          {loading === "cancel" ? "Cancelling…" : "Cancel Run"}
        </button>
      )}
      {error && <span className="text-sm text-red-600">{error}</span>}
    </div>
  );
}
