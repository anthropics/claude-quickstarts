import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { Employee } from "@/lib/types";
import EmployeeForm, { type EmployeeFormValues } from "../../_components/EmployeeForm";

export const dynamic = "force-dynamic";

export default function EditEmployeePage({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  if (!Number.isInteger(id) || id <= 0) notFound();

  const db = getDb();
  const emp = db.prepare("SELECT * FROM employees WHERE id = ?").get(id) as Employee | undefined;
  if (!emp) notFound();

  const user = getCurrentUser();
  if (!isHr(user)) {
    return (
      <div className="card max-w-lg">
        <h1 className="font-semibold">Access denied</h1>
        <p className="mt-1 text-sm text-gray-500">Only HR and admins can edit employees.</p>
        <Link href={`/employees/${id}`} className="btn-secondary mt-4">
          Back to profile
        </Link>
      </div>
    );
  }

  const departments = db.prepare("SELECT id, name FROM departments ORDER BY name").all() as {
    id: number;
    name: string;
  }[];
  const managers = db
    .prepare(
      "SELECT id, first_name || ' ' || last_name AS name FROM employees WHERE status != 'terminated' ORDER BY first_name, last_name"
    )
    .all() as { id: number; name: string }[];

  const initial: EmployeeFormValues = {
    id: emp.id,
    first_name: emp.first_name,
    last_name: emp.last_name,
    work_email: emp.work_email,
    employee_number: emp.employee_number,
    job_title: emp.job_title,
    department_id: emp.department_id,
    manager_id: emp.manager_id,
    employment_type: emp.employment_type,
    start_date: emp.start_date,
    probation_end_date: emp.probation_end_date,
    role: emp.role,
    phone: emp.phone,
    status: emp.status,
    personal_email: emp.personal_email,
    date_of_birth: emp.date_of_birth,
    gender: emp.gender,
    nationality: emp.nationality,
    address: emp.address,
    emergency_contact_name: emp.emergency_contact_name,
    emergency_contact_phone: emp.emergency_contact_phone,
  };

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <Link href={`/employees/${emp.id}`} className="text-sm font-medium text-brand-600 hover:underline">
          ← {emp.first_name} {emp.last_name}
        </Link>
        <h1 className="mt-1 text-2xl font-bold">
          Edit {emp.first_name} {emp.last_name}
        </h1>
        <p className="text-sm text-gray-500">{emp.employee_number}</p>
      </div>
      <EmployeeForm departments={departments} managers={managers} employee={initial} />
    </div>
  );
}
