"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface Props {
  employees: { id: number; name: string }[];
  templates: { id: number; name: string }[];
}

export default function StartOnboardingForm({ employees, templates }: Props) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setLoading(true);
    const fd = new FormData(e.currentTarget);
    const res = await fetch("/api/onboarding/instances", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        employee_id: Number(fd.get("employee_id")),
        template_id: Number(fd.get("template_id")),
      }),
    });
    setLoading(false);
    if (!res.ok) {
      const j = await res.json();
      setError(j.error ?? "Failed to start onboarding");
      return;
    }
    const { id } = await res.json();
    router.push(`/onboarding/${id}`);
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label className="label">Employee</label>
        <select name="employee_id" required className="input">
          <option value="">Select employee…</option>
          {employees.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
      </div>
      <div>
        <label className="label">Onboarding template</label>
        <select name="template_id" required className="input">
          {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button type="submit" disabled={loading} className="btn-primary w-full">
        {loading ? "Starting…" : "Start onboarding"}
      </button>
    </form>
  );
}
