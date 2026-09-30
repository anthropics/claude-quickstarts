import Link from "next/link";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import GenerateLetterForm from "../_components/GenerateLetterForm";

export const dynamic = "force-dynamic";

export default function GenerateLetterPage({
  searchParams,
}: {
  searchParams: { employee?: string };
}) {
  const user = getCurrentUser();
  if (!isHr(user)) {
    return (
      <div className="card max-w-lg">
        <h1 className="font-semibold">Access denied</h1>
        <p className="mt-1 text-sm text-gray-500">Only HR and admins can generate letters.</p>
        <Link href="/" className="btn-secondary mt-4">
          Back to dashboard
        </Link>
      </div>
    );
  }

  const db = getDb();
  const templates = db
    .prepare("SELECT id, name, type FROM letter_templates ORDER BY name")
    .all() as { id: number; name: string; type: string }[];
  const employees = db
    .prepare(
      `SELECT id, first_name || ' ' || last_name AS name, employee_number
       FROM employees WHERE status != 'terminated'
       ORDER BY first_name, last_name`
    )
    .all() as { id: number; name: string; employee_number: string }[];

  const preselected = Number(searchParams.employee);
  const initialEmployeeId =
    Number.isInteger(preselected) && employees.some((e) => e.id === preselected) ? preselected : null;

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <Link href="/letters" className="text-sm font-medium text-brand-600 hover:underline">
          ← HR Letters
        </Link>
        <h1 className="mt-1 text-2xl font-bold">Generate letter</h1>
        <p className="text-sm text-gray-500">
          Pick a template and an employee, preview the rendered letter, then issue it.
        </p>
      </div>
      <GenerateLetterForm templates={templates} employees={employees} initialEmployeeId={initialEmployeeId} />
    </div>
  );
}
