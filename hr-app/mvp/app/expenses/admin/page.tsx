import { getDb } from "@/lib/db";
import { getCurrentUser, canManage, isHr } from "@/lib/session";
import type { ExpenseCategory } from "@/lib/types";
import { formatRand } from "../_lib/format";
import ExpenseTabs from "../_components/ExpenseTabs";
import CategoryForm from "../_components/CategoryForm";

export const dynamic = "force-dynamic";

interface SpendRow {
  name: string;
  total: number;
  claims: number;
}

export default function ExpenseAdminPage() {
  const db = getDb();
  const user = getCurrentUser();
  const year = String(new Date().getFullYear());

  if (!isHr(user)) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Expense Admin</h1>
        <ExpenseTabs active="admin" showApprovals={canManage(user)} showAdmin={false} />
        <div className="card text-sm text-gray-600">
          This area is restricted to HR and admins. Please contact People &amp; Culture if you need a change to
          expense categories.
        </div>
      </div>
    );
  }

  const categories = db.prepare("SELECT * FROM expense_categories ORDER BY name").all() as ExpenseCategory[];

  const claimedStmt = db.prepare(
    `SELECT COALESCE(SUM(amount), 0) AS total FROM expense_claims
     WHERE category_id = ? AND status != 'rejected' AND strftime('%Y', expense_date) = ?`
  );
  const claimedByCategory = new Map(
    categories.map((c) => [c.id, (claimedStmt.get(c.id, year) as { total: number }).total])
  );

  // Reports: reimbursable spend = approved + reimbursed claims this year.
  const spendByCategory = db
    .prepare(
      `SELECT c.name, COALESCE(SUM(ec.amount), 0) AS total, COUNT(ec.id) AS claims
       FROM expense_claims ec
       JOIN expense_categories c ON c.id = ec.category_id
       WHERE ec.status IN ('approved', 'reimbursed') AND strftime('%Y', ec.expense_date) = ?
       GROUP BY c.id
       ORDER BY total DESC`
    )
    .all(year) as SpendRow[];

  const spendByDepartment = db
    .prepare(
      `SELECT COALESCE(d.name, 'No department') AS name, COALESCE(SUM(ec.amount), 0) AS total, COUNT(ec.id) AS claims
       FROM expense_claims ec
       JOIN employees e ON e.id = ec.employee_id
       LEFT JOIN departments d ON d.id = e.department_id
       WHERE ec.status IN ('approved', 'reimbursed') AND strftime('%Y', ec.expense_date) = ?
       GROUP BY d.id
       ORDER BY total DESC`
    )
    .all(year) as SpendRow[];

  const categoryTotal = spendByCategory.reduce((s, r) => s + r.total, 0);
  const departmentTotal = spendByDepartment.reduce((s, r) => s + r.total, 0);

  const yesNo = (v: number) =>
    v === 1 ? <span className="badge-green">Yes</span> : <span className="badge-gray">No</span>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Expense Admin</h1>
        <p className="text-sm text-gray-500">Manage expense categories and review spend for {year}.</p>
      </div>

      <ExpenseTabs active="admin" showApprovals={canManage(user)} showAdmin={true} />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <div className="card overflow-x-auto p-0">
            <table className="w-full">
              <thead className="border-b border-gray-200 bg-gray-50">
                <tr>
                  <th className="th">Name</th>
                  <th className="th">Code</th>
                  <th className="th">Monthly limit</th>
                  <th className="th">Receipt required</th>
                  <th className="th">Claimed in {year}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {categories.map((c) => (
                  <tr key={c.id}>
                    <td className="td font-medium text-gray-900">{c.name}</td>
                    <td className="td font-mono text-xs">{c.code}</td>
                    <td className="td whitespace-nowrap">
                      {c.monthly_limit !== null ? formatRand(c.monthly_limit) : <span className="text-gray-400">No limit</span>}
                    </td>
                    <td className="td">{yesNo(c.requires_receipt)}</td>
                    <td className="td whitespace-nowrap">{formatRand(claimedByCategory.get(c.id) ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h2 className="mb-3 font-semibold">Add category</h2>
            <CategoryForm />
          </div>
        </div>

        <div className="space-y-6">
          <div className="card p-0">
            <h2 className="px-4 pb-2 pt-4 font-semibold">Spend by category — {year}</h2>
            <table className="w-full">
              <thead className="border-b border-gray-200 bg-gray-50">
                <tr>
                  <th className="th">Category</th>
                  <th className="th text-right">Claims</th>
                  <th className="th text-right">Spend</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {spendByCategory.length === 0 && (
                  <tr>
                    <td className="td text-gray-500" colSpan={3}>
                      No approved spend yet in {year}.
                    </td>
                  </tr>
                )}
                {spendByCategory.map((r, i) => (
                  <tr key={i}>
                    <td className="td">{r.name}</td>
                    <td className="td text-right">{r.claims}</td>
                    <td className="td whitespace-nowrap text-right">{formatRand(r.total)}</td>
                  </tr>
                ))}
                {spendByCategory.length > 0 && (
                  <tr className="bg-gray-50 font-semibold">
                    <td className="td text-gray-900">Total</td>
                    <td className="td"></td>
                    <td className="td whitespace-nowrap text-right text-gray-900">{formatRand(categoryTotal)}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="card p-0">
            <h2 className="px-4 pb-2 pt-4 font-semibold">Spend by department — {year}</h2>
            <table className="w-full">
              <thead className="border-b border-gray-200 bg-gray-50">
                <tr>
                  <th className="th">Department</th>
                  <th className="th text-right">Claims</th>
                  <th className="th text-right">Spend</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {spendByDepartment.length === 0 && (
                  <tr>
                    <td className="td text-gray-500" colSpan={3}>
                      No approved spend yet in {year}.
                    </td>
                  </tr>
                )}
                {spendByDepartment.map((r, i) => (
                  <tr key={i}>
                    <td className="td">{r.name}</td>
                    <td className="td text-right">{r.claims}</td>
                    <td className="td whitespace-nowrap text-right">{formatRand(r.total)}</td>
                  </tr>
                ))}
                {spendByDepartment.length > 0 && (
                  <tr className="bg-gray-50 font-semibold">
                    <td className="td text-gray-900">Total</td>
                    <td className="td"></td>
                    <td className="td whitespace-nowrap text-right text-gray-900">{formatRand(departmentTotal)}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <p className="text-xs text-gray-400">
            Spend reports include approved and reimbursed claims; the &ldquo;Claimed&rdquo; column also counts pending
            claims.
          </p>
        </div>
      </div>
    </div>
  );
}
