"use client";

import { useRouter } from "next/navigation";

const TYPES = [
  { value: "individual", label: "Individual" },
  { value: "team", label: "Team" },
  { value: "company", label: "Company" },
];

const STATUSES = [
  { value: "not_started", label: "Not started" },
  { value: "in_progress", label: "In progress" },
  { value: "at_risk", label: "At risk" },
  { value: "achieved", label: "Achieved" },
  { value: "missed", label: "Missed" },
];

export default function GoalFilters({ type, status }: { type: string; status: string }) {
  const router = useRouter();

  function apply(nextType: string, nextStatus: string) {
    const params = new URLSearchParams();
    if (nextType) params.set("type", nextType);
    if (nextStatus) params.set("status", nextStatus);
    const qs = params.toString();
    router.push(qs ? `/performance/goals?${qs}` : "/performance/goals");
  }

  return (
    <div className="flex flex-col gap-3 sm:flex-row">
      <select
        className="input sm:w-48"
        value={type}
        onChange={(e) => apply(e.target.value, status)}
        aria-label="Filter by goal type"
      >
        <option value="">All types</option>
        {TYPES.map((t) => (
          <option key={t.value} value={t.value}>
            {t.label}
          </option>
        ))}
      </select>
      <select
        className="input sm:w-48"
        value={status}
        onChange={(e) => apply(type, e.target.value)}
        aria-label="Filter by goal status"
      >
        <option value="">All statuses</option>
        {STATUSES.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </select>
    </div>
  );
}
