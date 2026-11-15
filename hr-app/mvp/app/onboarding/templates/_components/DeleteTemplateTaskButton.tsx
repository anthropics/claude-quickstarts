"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface DeleteTemplateTaskButtonProps {
  templateId: number;
  taskId: number;
}

export default function DeleteTemplateTaskButton({ templateId, taskId }: DeleteTemplateTaskButtonProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDelete() {
    if (!confirm("Delete this task from the template?")) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/onboarding/templates/${templateId}/tasks/${taskId}`, {
        method: "DELETE",
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Failed to delete task.");
        return;
      }
      router.refresh();
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <span>
      <button
        className="btn-danger text-xs"
        onClick={handleDelete}
        disabled={loading}
      >
        {loading ? "Deleting…" : "Delete"}
      </button>
      {error && <span className="ml-2 text-xs text-red-600">{error}</span>}
    </span>
  );
}
