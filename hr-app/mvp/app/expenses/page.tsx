import { getDb } from "@/lib/db";
import { getCurrentUser, canManage, isHr } from "@/lib/session";
import type { ExpenseCategory } from "@/lib/types";
import { claimStatusBadgeClass, formatRand } from "./_lib/format";
import { monthCategoryTotal } from "./_lib/data";
import ExpenseTabs from "./_components/ExpenseTabs";
import ClaimForm from "./_components/ClaimForm";
import DeleteClaimButton from "./_components/DeleteClaimButton";

export const dynamic = "force-dynamic";

interface MyClaimRow {
  id: number;
  expense_date: string;
  amount: number;
  description: string;
  receipt_filename: string | null;
  status: string;
  decision_note: string | null;
  category_name: string;
}

export default function MyExpensesPage() {
  const db = getDb();
  const user = getCurrentUser();
  const today = new Date().toISOString().slice(0, 10);
  const year = today.slice(0, 4);
  const month = today.slice(0, 7);

  const sumByStatus = db.prepare(
    "SELECT COALESCE(SUM(amount), 0) AS total FROM expense_claims WHERE employee_id = ? AND status = ?"
  );
  const pendingTotal = (sumByStatus.get(user.id, "pending") as { total: number }).total;
  const approvedTotal = (sumByStatus.get(user.id, "approved") as { total: number }).total;
  const reimbursedThisYear = (
    db
      .prepare(
        `SELECT COALESCE(SUM(amount), 0) AS total FROM expense_claims
         WHERE employee_id = ? AND status = 'reimbursed' AND strftime('%Y', expense_date) = ?`
      )
      .get(user.id, year) as { total: number }
  ).total;

  const categories = db
    .prepare("SELECT * FROM expense_categories ORDER BY name")
    .all() as ExpenseCategory[];

  const claims = db
    .prepare(
      `SELECT ec.id, ec.expense_date, ec.amount, ec.description, ec.receipt_filename, ec.status, ec.decision_note,
              c.name AS category_name
       FROM expense_claims ec
       JOIN expense_categories c ON c.id = ec.category_id
       WHERE ec.employee_id = ?
       ORDER BY ec.expense_date DESC, ec.id DESC`
    )
    .all(user.id) as MyClaimRow[];

  const budgets = categories
    .filter((c) => c.monthly_limit !== null)
    .map((c) => {
      const used = monthCategoryTotal(user.id, c.id, month);
      const limit = c.monthly_limit as number;
      return { category: c, used, limit, pct: Math.min(100, (used / limit) * 100), over: used > limit };
    });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Expenses</h1>
        <p className="text-sm text-gray-500">Submit and track your expense claims.</p>
      </div>

      <ExpenseTabs active="my" showApprovals={canManage(user)} showAdmin={isHr(user)} />

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Pending approval</p>
          <p className="mt-1 text-3xl font-bold">{formatRand(pendingTotal)}</p>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Approved — awaiting reimbursement</p>
          <p className="mt-1 text-3xl font-bold">{formatRand(approvedTotal)}</p>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Reimbursed in {year}</p>
          <p className="mt-1 text-3xl font-bold">{formatRand(reimbursedThisYear)}</p>
        </div>
      </div>

      <ClaimForm
        categories={categories.map((c) => ({
          id: c.id,
          name: c.name,
          code: c.code,
          monthly_limit: c.monthly_limit,
          requires_receipt: c.requires_receipt,
        }))}
      />

      {budgets.length > 0 && (
        <div className="card">
          <h2 className="mb-3 font-semibold">My budgets — {month}</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {budgets.map((b) => (
              <div key={b.category.id}>
                <div className="flex items-baseline justify-between gap-2">
                  <p className="text-sm font-medium text-gray-700">{b.category.name}</p>
                  {b.over && <span className="badge-red">Over limit</span>}
                </div>
                <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-gray-100">
                  <div
                    className={`h-full rounded-full ${b.over ? "bg-red-600" : "bg-brand-600"}`}
                    style={{ width: `${b.pct}%` }}
                  />
                </div>
                <p className="mt-1 text-xs text-gray-500">
                  {formatRand(b.used)} of {formatRand(b.limit)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="border-b border-gray-200 bg-gray-50">
            <tr>
              <th className="th">Date</th>
              <th className="th">Category</th>
              <th className="th">Description</th>
              <th className="th">Amount</th>
              <th className="th">Receipt</th>
              <th className="th">Status</th>
              <th className="th"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {claims.length === 0 && (
              <tr>
                <td className="td text-gray-500" colSpan={7}>
                  No expense claims yet.
                </td>
              </tr>
            )}
            {claims.map((c) => (
              <tr key={c.id}>
                <td className="td whitespace-nowrap">{c.expense_date}</td>
                <td className="td whitespace-nowrap">{c.category_name}</td>
                <td className="td max-w-xs">
                  {c.description}
                  {c.decision_note && <p className="text-xs text-gray-400">Note: {c.decision_note}</p>}
                </td>
                <td className="td whitespace-nowrap font-medium">{formatRand(c.amount)}</td>
                <td className="td max-w-[10rem] truncate font-mono text-xs">
                  {c.receipt_filename ?? <span className="text-gray-400">—</span>}
                </td>
                <td className="td">
                  <span className={`${claimStatusBadgeClass(c.status)} capitalize`}>{c.status}</span>
                </td>
                <td className="td text-right">{c.status === "pending" && <DeleteClaimButton claimId={c.id} />}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
