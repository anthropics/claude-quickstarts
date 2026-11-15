import Link from "next/link";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import DirectoryFilters from "./_components/DirectoryFilters";
import StatusBadge from "./_components/StatusBadge";

export const dynamic = "force-dynamic";

interface Row {
  id: number;
  first_name: string;
  last_name: string;
  employee_number: string;
  job_title: string;
  department: string | null;
  status: string;
  start_date: string;
}

export default function EmployeesPage({
  searchParams,
}: {
  searchParams: { q?: string; dept?: string };
}) {
  const db = getDb();
  const user = getCurrentUser();
  const q = (searchParams.q ?? "").trim();
  const deptId = Number(searchParams.dept) || 0;

  const where: string[] = [];
  const args: (string | number)[] = [];
  if (q) {
    where.push("(e.first_name || ' ' || e.last_name) LIKE ?");
    args.push(`%${q}%`);
  }
  if (deptId) {
    where.push("e.department_id = ?");
    args.push(deptId);
  }

  const rows = db
    .prepare(
      `SELECT e.id, e.first_name, e.last_name, e.employee_number, e.job_title, e.status, e.start_date,
              d.name AS department
       FROM employees e
       LEFT JOIN departments d ON d.id = e.department_id
       ${where.length ? `WHERE ${where.join(" AND ")}` : ""}
       ORDER BY e.first_name, e.last_name`
    )
    .all(...args) as Row[];

  const departments = db.prepare("SELECT id, name FROM departments ORDER BY name").all() as {
    id: number;
    name: string;
  }[];

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Employees</h1>
          <p className="text-sm text-gray-500">
            {rows.length} {rows.length === 1 ? "person" : "people"} in the directory.
          </p>
        </div>
        {isHr(user) && (
          <Link href="/employees/new" className="btn-primary">
            Add employee
          </Link>
        )}
      </div>

      <DirectoryFilters departments={departments} initialQ={q} initialDept={deptId ? String(deptId) : ""} />

      <div className="card overflow-x-auto p-0">
        <table className="w-full min-w-[720px]">
          <thead className="border-b border-gray-200 bg-gray-50">
            <tr>
              <th className="th">Name</th>
              <th className="th">Employee #</th>
              <th className="th">Job title</th>
              <th className="th">Department</th>
              <th className="th">Status</th>
              <th className="th">Start date</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {rows.length === 0 && (
              <tr>
                <td className="td py-8 text-center text-gray-500" colSpan={6}>
                  No employees match your search.
                </td>
              </tr>
            )}
            {rows.map((e) => (
              <tr key={e.id} className="hover:bg-gray-50">
                <td className="td">
                  <Link href={`/employees/${e.id}`} className="font-medium text-brand-600 hover:underline">
                    {e.first_name} {e.last_name}
                  </Link>
                </td>
                <td className="td">{e.employee_number}</td>
                <td className="td">{e.job_title}</td>
                <td className="td">{e.department ?? "—"}</td>
                <td className="td">
                  <StatusBadge status={e.status} />
                </td>
                <td className="td">{e.start_date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
