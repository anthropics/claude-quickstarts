"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { ApplicationStage } from "@/lib/types";

const VALID_NEXT: Record<ApplicationStage, ApplicationStage[]> = {
  applied: ["screening", "rejected", "withdrawn"],
  screening: ["phone_screen", "interview", "rejected", "withdrawn"],
  phone_screen: ["interview", "rejected", "withdrawn"],
  interview: ["assessment", "offer", "rejected", "withdrawn"],
  assessment: ["offer", "rejected", "withdrawn"],
  offer: ["hired", "rejected", "withdrawn"],
  hired: [],
  rejected: [],
  withdrawn: [],
};

const STAGE_LABELS: Record<string, string> = {
  applied: "Applied",
  screening: "Screening",
  phone_screen: "Phone Screen",
  interview: "Interview",
  assessment: "Assessment",
  offer: "Offer",
  hired: "Hired",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

interface StageActionsProps {
  appId: number;
  currentStage: ApplicationStage;
}

export default function StageActions({ appId, currentStage }: StageActionsProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function moveToStage(stage: ApplicationStage) {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/recruitment/applications/${appId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage }),
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
    }
    setLoading(false);
  }

  const nextStages = VALID_NEXT[currentStage] ?? [];
  const progressStages = nextStages.filter((s) => s !== "rejected" && s !== "withdrawn");
  const exitStages = nextStages.filter((s) => s === "rejected" || s === "withdrawn");

  if (nextStages.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {error && <span className="text-xs text-red-600">{error}</span>}
      {progressStages.map((s) => (
        <button
          key={s}
          onClick={() => moveToStage(s)}
          disabled={loading}
          className="btn-primary text-sm"
        >
          Move to {STAGE_LABELS[s]}
        </button>
      ))}
      {exitStages.map((s) => (
        <button
          key={s}
          onClick={() => moveToStage(s)}
          disabled={loading}
          className="btn-danger text-sm"
        >
          {STAGE_LABELS[s]}
        </button>
      ))}
    </div>
  );
}
