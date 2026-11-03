import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { Employee } from "@/lib/types";
import StatusBadge from "../_components/StatusBadge";
import DocumentsSection, { type DocumentRow } from "../_components/DocumentsSection";
import { CHANGE_REASONS, EMPLOYMENT_TYPES, labelFor, ROLES } from "../_components/labels";

export const dynamic = "force-dynamic";

type ProfileRow = Employee & {
  department_name: string | null;
  manager_name: string | null;
};

interface HistoryRow {
  id: number;
  job_title: string;
  employment_type: string;
  effective_from: string;
  effective_to: string | null;
  change_reason: string | null;
  department_name: string | null;
  manager_name: string | null;
}

function reasonBadge(reason: string | null) {
  switch (reason) {
    case "hired":
      return <span className="badge-green">Hired</span>;
    case "promotion":
      return <span className="badge-blue">Promotion</span>;
    case "transfer":
      return <span className="badge-yellow">Transfer</span>;
    case "restructure":
      return <span className="badge-red">Restructure</span>;
    case "correction":
      return <span className="badge-gray">Correction</span>;
    default:
      return <span className="badge-gray">{labelFor(CHANGE_REASONS, reason)}</span>;
  }
}

function Field({ label, value }: { label: string; value?: React.ReactNode }) {
  return (
    <div>
      <dt className="label">{label}</dt>
      <dd className="text-sm text-gray-700">{value ?? "—"}</dd>
    </div>
  );
}

export default function EmployeeProfilePage({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  if (!Number.isInteger(id) || id <= 0) notFound();

  const db = getDb();
  const user = getCurrentUser();
  const emp = db
    .prepare(
      `SELECT e.*, d.name AS department_name, m.first_name || ' ' || m.last_name AS manager_name
       FROM employees e
       LEFT JOIN departments d ON d.id = e.department_id
       LEFT JOIN employees m ON m.id = e.manager_id
       WHERE e.id = ?`
    )
    .get(id) as ProfileRow | undefined;
  if (!emp) notFound();

  const initials = `${emp.first_name[0] ?? ""}${emp.last_name[0] ?? ""}`.toUpperCase();
  const onProbation =
    !!emp.probation_end_date && emp.probation_end_date >= new Date().toISOString().slice(0, 10);

  // Document vault access: HR sees all, a manager their direct reports', an
  // employee only their own. Enforced here and again in the API routes.
  const canViewDocuments = isHr(user) || user.id === emp.id || emp.manager_id === user.id;
  const documents = canViewDocuments
    ? (db
        .prepare(
          `SELECT ed.id, ed.title, ed.category, ed.created_at, ed.file_id,
                  f.original_name, f.size_bytes,
                  u.first_name || ' ' || u.last_name AS uploaded_by_name
           FROM employee_documents ed
           JOIN files f ON f.id = ed.file_id
           LEFT JOIN employees u ON u.id = ed.uploaded_by
           WHERE ed.employee_id = ?
           ORDER BY ed.created_at DESC, ed.id DESC`
        )
        .all(emp.id) as DocumentRow[])
    : [];

  const history = db
    .prepare(
      `SELECT h.id, h.job_title, h.employment_type, h.effective_from, h.effective_to, h.change_reason,
              d.name AS department_name,
              m.first_name || ' ' || m.last_name AS manager_name
       FROM employment_history h
       LEFT JOIN departments d ON d.id = h.department_id
       LEFT JOIN employees m ON m.id = h.manager_id
       WHERE h.employee_id = ?
       ORDER BY h.effective_from DESC, h.id DESC`
    )
    .all(emp.id) as HistoryRow[];

  return (
    <div className="space-y-6">
      <Link href="/employees" className="text-sm font-medium text-brand-600 hover:underline">
        ← Employees
      </Link>

      <div className="card flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-brand-600 text-lg font-bold text-white">
            {initials}
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-bold">
                {emp.first_name} {emp.last_name}
              </h1>
              <StatusBadge status={emp.status} />
              {onProbation && <span className="badge-blue">On probation</span>}
            </div>
            <p className="text-sm text-gray-500">
              {emp.job_title}
              {emp.department_name ? ` · ${emp.department_name}` : ""} · {emp.employee_number}
            </p>
          </div>
        </div>
        {isHr(user) && (
          <div className="flex gap-2 self-start sm:self-auto">
            <Link href={`/letters/generate?employee=${emp.id}`} className="btn-secondary">
              Generate letter
            </Link>
            <Link href={`/employees/${emp.id}/edit`} className="btn-secondary">
              Edit
            </Link>
          </div>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="card">
          <h2 className="mb-3 font-semibold">Personal &amp; contact</h2>
          <dl className="space-y-3">
            <Field
              label="Work email"
              value={
                <a href={`mailto:${emp.work_email}`} className="text-brand-600 hover:underline">
                  {emp.work_email}
                </a>
              }
            />
            <Field label="Personal email" value={emp.personal_email} />
            <Field label="Phone" value={emp.phone} />
            <Field label="Date of birth" value={emp.date_of_birth} />
            <Field label="Gender" value={emp.gender} />
            <Field label="Nationality" value={emp.nationality} />
            <Field label="Address" value={emp.address} />
          </dl>
        </div>

        <div className="card">
          <h2 className="mb-3 font-semibold">Job info</h2>
          <dl className="space-y-3">
            <Field label="Job title" value={emp.job_title} />
            <Field label="Department" value={emp.department_name} />
            <Field
              label="Manager"
              value={
                emp.manager_id && emp.manager_name ? (
                  <Link href={`/employees/${emp.manager_id}`} className="text-brand-600 hover:underline">
                    {emp.manager_name}
                  </Link>
                ) : (
                  "—"
                )
              }
            />
            <Field label="Employment type" value={labelFor(EMPLOYMENT_TYPES, emp.employment_type)} />
            <Field label="Start date" value={emp.start_date} />
            <Field label="Probation end date" value={emp.probation_end_date} />
            <Field label="System role" value={labelFor(ROLES, emp.role)} />
          </dl>
        </div>

        <div className="card">
          <h2 className="mb-3 font-semibold">Emergency contact</h2>
          {emp.emergency_contact_name || emp.emergency_contact_phone ? (
            <dl className="space-y-3">
              <Field label="Name" value={emp.emergency_contact_name} />
              <Field label="Phone" value={emp.emergency_contact_phone} />
            </dl>
          ) : (
            <p className="text-sm text-gray-500">No emergency contact on file.</p>
          )}
        </div>
      </div>

      {canViewDocuments && (
        <DocumentsSection
          employeeId={emp.id}
          documents={documents}
          canUpload={isHr(user) || user.id === emp.id}
          canDelete={isHr(user)}
        />
      )}

      <div className="card">
        <h2 className="mb-3 font-semibold">History</h2>
        {history.length === 0 ? (
          <p className="text-sm text-gray-500">No employment history recorded.</p>
        ) : (
          <ol className="relative ml-2 space-y-5 border-l border-gray-200 pl-6">
            {history.map((h, i) => (
              <li key={h.id} className="relative">
                <span
                  className={`absolute -left-[31px] top-1.5 h-2.5 w-2.5 rounded-full ${
                    i === 0 ? "bg-brand-600" : "bg-gray-300"
                  }`}
                />
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-gray-900">{h.job_title}</span>
                  {reasonBadge(h.change_reason)}
                  {h.effective_to === null && <span className="badge-green">Current</span>}
                </div>
                <p className="mt-0.5 text-sm text-gray-500">
                  {h.department_name ?? "No department"}
                  {h.manager_name ? ` · Reports to ${h.manager_name}` : " · No manager"}
                  {" · "}
                  {labelFor(EMPLOYMENT_TYPES, h.employment_type)}
                </p>
                <p className="text-xs text-gray-400">
                  {h.effective_from} → {h.effective_to ?? "present"}
                </p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
