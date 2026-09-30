"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface TaskCompleteWidgetProps {
  taskId: number;
  currentNotes: string | null;
}

export default function TaskCompleteWidget({ taskId, currentNotes }: TaskCompleteWidgetProps) {
  const router = useRouter();
  const [notes, setNotes] = useState(currentNotes ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleComplete() {
    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`/api/onboarding/tasks/${taskId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "completed", notes: notes || undefined }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Failed to complete task.");
        return;
      }
      router.refresh();
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mt-3 space-y-2">
      <textarea
        className="input text-sm"
        rows={2}
        placeholder="Notes (optional)…"
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
      />
      {error && (
        <p className="text-sm text-red-600">{error}</p>
      )}
      <button
        className="btn-primary text-sm"
        onClick={handleComplete}
        disabled={saving}
      >
        {saving ? "Saving…" : "Mark complete"}
      </button>
    </div>
  );
}
