"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface EmployeeOption {
  id: number;
  name: string;
}

interface HireFormProps {
  appId: number;
  candidateName: string;
  candidateEmail: string;
  jobTitle: string;
  departmentName: string | null;
  salary: number | null;
  suggestedEmployeeNumber: string;
  defaultStartDate: string;
  defaultManagerId: number | null;
  employees: EmployeeOption[];
}

export default function HireForm({
  appId,
  candidateName,
  candidateEmail,
  jobTitle,
  departmentName,
  salary,
  suggestedEmployeeNumber,
  defaultStartDate,
  defaultManagerId,
  employees,
}: HireFormProps) {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    setError(null);

    const data = new FormData(e.currentTarget);
    const managerRaw = data.get("manager_id") as string;

    const payload = {
      employee_number: data.get("employee_number") as string,
      manager_id: managerRaw ? Number(managerRaw) : null,
      role: data.get("role") as string,
      probation_months: Number(data.get("probation_months")),
      start_date: data.get("start_date") as string,
    };

    try {
      const res = await fetch(`/api/recruitment/applications/${appId}/hire`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (!res.ok) {
        setError(json.error ?? "Failed to convert to employee.");
        setSaving(false);
        return;
      }
      router.push(`/employees/${json.employee_id}`);
      router.refresh();
    } catch {
      setError("Network error. Please try again.");
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Pre-filled, read-only details from candidate / posting / offer */}
      <dl className="grid gap-3 rounded-lg border border-gray-100 bg-gray-50 p-4 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Name</dt>
          <dd className="mt-0.5 font-medium text-gray-900">{candidateName}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Work email</dt>
          <dd className="mt-0.5 text-gray-900">{candidateEmail}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Job title</dt>
          <dd className="mt-0.5 text-gray-900">{jobTitle}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Department</dt>
          <dd className="mt-0.5 text-gray-900">{departmentName ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Basic salary (from offer)</dt>
          <dd className="mt-0.5 font-semibold text-gray-900">
            {salary != null ? `R ${salary.toLocaleString("en-ZA")} / month` : "No accepted offer on file"}
          </dd>
        </div>
      </dl>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="label">Employee number *</label>
          <input
            name="employee_number"
            required
            defaultValue={suggestedEmployeeNumber}
            className="input"
          />
        </div>
        <div>
          <label className="label">Start date *</label>
          <input name="start_date" type="date" required defaultValue={defaultStartDate} className="input" />
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <div>
          <label className="label">Manager</label>
          <select name="manager_id" className="input" defaultValue={defaultManagerId ?? ""}>
            <option value="">No manager</option>
            {employees.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label">Role</label>
          <select name="role" className="input" defaultValue="employee">
            <option value="employee">Employee</option>
            <option value="manager">Manager</option>
            <option value="hr">HR</option>
            <option value="admin">Admin</option>
          </select>
        </div>
        <div>
          <label className="label">Probation</label>
          <select name="probation_months" className="input" defaultValue="3">
            <option value="0">None</option>
            <option value="3">3 months</option>
            <option value="6">6 months</option>
          </select>
        </div>
      </div>

      <div className="flex gap-2 pt-1">
        <button type="submit" disabled={saving} className="btn-primary">
          {saving ? "Converting…" : "Create employee"}
        </button>
      </div>
    </form>
  );
}
