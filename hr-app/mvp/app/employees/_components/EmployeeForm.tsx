"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { CHANGE_REASONS, EMPLOYMENT_TYPES, ROLES, STATUSES } from "./labels";

export interface EmployeeFormValues {
  id: number;
  first_name: string;
  last_name: string;
  work_email: string;
  employee_number: string;
  job_title: string;
  department_id: number | null;
  manager_id: number | null;
  employment_type: string;
  start_date: string;
  probation_end_date: string | null;
  role: string;
  phone: string | null;
  status: string;
  personal_email: string | null;
  date_of_birth: string | null;
  gender: string | null;
  nationality: string | null;
  address: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
}

interface Props {
  departments: { id: number; name: string }[];
  managers: { id: number; name: string }[];
  /** When provided the form edits this employee, otherwise it creates a new one. */
  employee?: EmployeeFormValues;
}

export default function EmployeeForm({ departments, managers, employee }: Props) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const isEdit = !!employee;

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSaving(true);

    const fd = new FormData(e.currentTarget);
    const str = (name: string) => (fd.get(name) as string | null)?.trim() ?? "";
    const opt = (name: string) => str(name) || null;
    const num = (name: string) => (str(name) ? Number(str(name)) : null);

    const payload: Record<string, unknown> = {
      first_name: str("first_name"),
      last_name: str("last_name"),
      work_email: str("work_email"),
      employee_number: str("employee_number"),
      job_title: str("job_title"),
      department_id: num("department_id"),
      manager_id: num("manager_id"),
      employment_type: str("employment_type"),
      start_date: str("start_date"),
      probation_end_date: opt("probation_end_date"),
      role: str("role"),
      phone: opt("phone"),
    };
    if (isEdit) {
      Object.assign(payload, {
        change_reason: str("change_reason"),
        status: str("status"),
        personal_email: opt("personal_email"),
        date_of_birth: opt("date_of_birth"),
        gender: opt("gender"),
        nationality: opt("nationality"),
        address: opt("address"),
        emergency_contact_name: opt("emergency_contact_name"),
        emergency_contact_phone: opt("emergency_contact_phone"),
      });
    }

    try {
      const res = await fetch(isEdit ? `/api/employees/${employee.id}` : "/api/employees", {
        method: isEdit ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = (await res.json()) as { id?: number; error?: string };
      if (!res.ok) {
        setError(data.error ?? "Something went wrong.");
        setSaving(false);
        return;
      }
      router.push(`/employees/${isEdit ? employee.id : data.id}`);
      router.refresh();
    } catch {
      setError("Network error — please try again.");
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      <div className="card">
        <h2 className="mb-4 font-semibold">Basic details</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="first_name">First name *</label>
            <input id="first_name" name="first_name" className="input" required defaultValue={employee?.first_name} />
          </div>
          <div>
            <label className="label" htmlFor="last_name">Last name *</label>
            <input id="last_name" name="last_name" className="input" required defaultValue={employee?.last_name} />
          </div>
          <div>
            <label className="label" htmlFor="work_email">Work email *</label>
            <input id="work_email" name="work_email" type="email" className="input" required defaultValue={employee?.work_email} />
          </div>
          <div>
            <label className="label" htmlFor="employee_number">Employee number *</label>
            <input id="employee_number" name="employee_number" className="input" required defaultValue={employee?.employee_number} />
          </div>
          <div>
            <label className="label" htmlFor="phone">Phone</label>
            <input id="phone" name="phone" type="tel" className="input" defaultValue={employee?.phone ?? ""} />
          </div>
          <div>
            <label className="label" htmlFor="role">Role *</label>
            <select id="role" name="role" className="input" defaultValue={employee?.role ?? "employee"}>
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="mb-4 font-semibold">Job details</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="label" htmlFor="job_title">Job title *</label>
            <input id="job_title" name="job_title" className="input" required defaultValue={employee?.job_title} />
          </div>
          <div>
            <label className="label" htmlFor="department_id">Department</label>
            <select id="department_id" name="department_id" className="input" defaultValue={employee?.department_id ?? ""}>
              <option value="">No department</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="manager_id">Manager</label>
            <select id="manager_id" name="manager_id" className="input" defaultValue={employee?.manager_id ?? ""}>
              <option value="">No manager</option>
              {managers
                .filter((m) => m.id !== employee?.id)
                .map((m) => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="employment_type">Employment type *</label>
            <select id="employment_type" name="employment_type" className="input" defaultValue={employee?.employment_type ?? "full_time"}>
              {EMPLOYMENT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="start_date">Start date *</label>
            <input id="start_date" name="start_date" type="date" className="input" required defaultValue={employee?.start_date} />
          </div>
          <div>
            <label className="label" htmlFor="probation_end_date">Probation end date</label>
            <input id="probation_end_date" name="probation_end_date" type="date" className="input" defaultValue={employee?.probation_end_date ?? ""} />
          </div>
          {isEdit && (
            <div>
              <label className="label" htmlFor="status">Status *</label>
              <select id="status" name="status" className="input" defaultValue={employee?.status ?? "active"}>
                {STATUSES.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
          )}
          {isEdit && (
            <div>
              <label className="label" htmlFor="change_reason">Reason for change</label>
              <select id="change_reason" name="change_reason" className="input" defaultValue="correction">
                {CHANGE_REASONS.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
              <p className="mt-1 text-xs text-gray-400">
                Recorded in employment history when job title, department, manager or employment type changes.
              </p>
            </div>
          )}
        </div>
      </div>

      {isEdit && (
        <>
          <div className="card">
            <h2 className="mb-4 font-semibold">Personal details</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="label" htmlFor="personal_email">Personal email</label>
                <input id="personal_email" name="personal_email" type="email" className="input" defaultValue={employee?.personal_email ?? ""} />
              </div>
              <div>
                <label className="label" htmlFor="date_of_birth">Date of birth</label>
                <input id="date_of_birth" name="date_of_birth" type="date" className="input" defaultValue={employee?.date_of_birth ?? ""} />
              </div>
              <div>
                <label className="label" htmlFor="gender">Gender</label>
                <input id="gender" name="gender" className="input" defaultValue={employee?.gender ?? ""} />
              </div>
              <div>
                <label className="label" htmlFor="nationality">Nationality</label>
                <input id="nationality" name="nationality" className="input" defaultValue={employee?.nationality ?? ""} />
              </div>
              <div className="sm:col-span-2">
                <label className="label" htmlFor="address">Address</label>
                <input id="address" name="address" className="input" defaultValue={employee?.address ?? ""} />
              </div>
            </div>
          </div>

          <div className="card">
            <h2 className="mb-4 font-semibold">Emergency contact</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="label" htmlFor="emergency_contact_name">Name</label>
                <input id="emergency_contact_name" name="emergency_contact_name" className="input" defaultValue={employee?.emergency_contact_name ?? ""} />
              </div>
              <div>
                <label className="label" htmlFor="emergency_contact_phone">Phone</label>
                <input id="emergency_contact_phone" name="emergency_contact_phone" type="tel" className="input" defaultValue={employee?.emergency_contact_phone ?? ""} />
              </div>
            </div>
          </div>
        </>
      )}

      <div className="flex items-center gap-3">
        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? "Saving…" : isEdit ? "Save changes" : "Create employee"}
        </button>
        <Link href={isEdit ? `/employees/${employee.id}` : "/employees"} className="btn-secondary">
          Cancel
        </Link>
      </div>
    </form>
  );
}
