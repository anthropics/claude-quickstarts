"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Props {
  periodStart: string; // Monday, YYYY-MM-DD
  label?: string;
}

export default function SubmitTimesheetButton({ periodStart, label = "Submit timesheet" }: Props) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setPending(true);
    setError(null);
    try {
      const res = await fetch("/api/time/timesheets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ period_start: periodStart }),
      });
      if (!res.ok) {
        const data = (await res.json().catch(() => null)) as { error?: string } | null;
        setError(data?.error ?? "Something went wrong.");
      }
      router.refresh();
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button className="btn-primary" disabled={pending} onClick={submit}>
        {pending ? "Submitting…" : label}
      </button>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
