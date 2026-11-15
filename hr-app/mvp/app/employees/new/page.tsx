import Link from "next/link";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import EmployeeForm from "../_components/EmployeeForm";

export const dynamic = "force-dynamic";

export default function NewEmployeePage() {
  const user = getCurrentUser();
  if (!isHr(user)) {
    return (
      <div className="card max-w-lg">
        <h1 className="font-semibold">Access denied</h1>
        <p className="mt-1 text-sm text-gray-500">Only HR and admins can add employees.</p>
        <Link href="/employees" className="btn-secondary mt-4">
          Back to directory
        </Link>
      </div>
    );
  }

  const db = getDb();
  const departments = db.prepare("SELECT id, name FROM departments ORDER BY name").all() as {
    id: number;
    name: string;
  }[];
  const managers = db
    .prepare(
      "SELECT id, first_name || ' ' || last_name AS name FROM employees WHERE status != 'terminated' ORDER BY first_name, last_name"
    )
    .all() as { id: number; name: string }[];

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <Link href="/employees" className="text-sm font-medium text-brand-600 hover:underline">
          ← Employees
        </Link>
        <h1 className="mt-1 text-2xl font-bold">Add employee</h1>
        <p className="text-sm text-gray-500">Create a new employee record.</p>
      </div>
      <EmployeeForm departments={departments} managers={managers} />
    </div>
  );
}
