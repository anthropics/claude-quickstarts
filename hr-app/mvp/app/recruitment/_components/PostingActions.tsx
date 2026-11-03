"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface PostingActionsProps {
  postingId: number;
  status: string;
  isHr: boolean;
}

export default function PostingActions({ postingId, status, isHr }: PostingActionsProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function changeStatus(newStatus: string) {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/recruitment/postings/${postingId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      const json = await res.json();
      if (!res.ok) {
        setError(json.error ?? "Failed.");
        setLoading(false);
        return;
      }
      router.refresh();
    } catch {
      setError("Network error.");
      setLoading(false);
    }
    setLoading(false);
  }

  if (!isHr) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {error && <span className="text-xs text-red-600">{error}</span>}
      {status === "draft" && (
        <button
          onClick={() => changeStatus("open")}
          disabled={loading}
          className="btn-primary"
        >
          Publish
        </button>
      )}
      {status === "open" && (
        <button
          onClick={() => changeStatus("closed")}
          disabled={loading}
          className="btn-danger"
        >
          Close posting
        </button>
      )}
      {status === "on_hold" && (
        <button
          onClick={() => changeStatus("open")}
          disabled={loading}
          className="btn-secondary"
        >
          Re-open
        </button>
      )}
    </div>
  );
}
