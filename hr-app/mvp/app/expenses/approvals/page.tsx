import { getDb } from "@/lib/db";
import { getCurrentUser, canManage, isHr } from "@/lib/session";
import { formatRand } from "../_lib/format";
import { monthCategoryTotal } from "../_lib/data";
import ExpenseTabs from "../_components/ExpenseTabs";
import ClaimDecisionButtons from "../_components/ClaimDecisionButtons";
import ReimburseButton from "../_components/ReimburseButton";

export const dynamic = "force-dynamic";

interface PendingRow {
  id: number;
  employee_id: number;
  category_id: number;
  amount: number;
  expense_date: string;
  description: string;
  receipt_filename: string | null;
  employee_name: string;
  job_title: string;
  category_name: string;
  monthly_limit: number | null;
}

interface ApprovedRow {
  id: number;
  amount: number;
  expense_date: string;
  description: string;
  decided_at: string | null;
  employee_name: string;
  category_name: string;
}

export default function ExpenseApprovalsPage() {
  const db = getDb();
  const user = getCurrentUser();

  if (!canManage(user)) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Expense Approvals</h1>
        <ExpenseTabs active="approvals" showApprovals={true} showAdmin={false} />
        <div className="card text-sm text-gray-600">
          You don&apos;t have any approval permissions. Expense claims are approved by managers and HR.
        </div>
      </div>
    );
  }

  const baseSelect = `
    SELECT ec.id, ec.employee_id, ec.category_id, ec.amount, ec.expense_date, ec.description, ec.receipt_filename,
           e.first_name || ' ' || e.last_name AS employee_name, e.job_title,
           c.name AS category_name, c.monthly_limit
    FROM expense_claims ec
    JOIN employees e ON e.id = ec.employee_id
    JOIN expense_categories c ON c.id = ec.category_id
    WHERE ec.status = 'pending'`;

  const pending = (
    isHr(user)
      ? db.prepare(`${baseSelect} ORDER BY ec.expense_date, ec.id`).all()
      : db.prepare(`${baseSelect} AND e.manager_id = ? ORDER BY ec.expense_date, ec.id`).all(user.id)
  ) as PendingRow[];

  const awaitingReimbursement = isHr(user)
    ? (db
        .prepare(
          `SELECT ec.id, ec.amount, ec.expense_date, ec.description, ec.decided_at,
                  e.first_name || ' ' || e.last_name AS employee_name,
                  c.name AS category_name
           FROM expense_claims ec
           JOIN employees e ON e.id = ec.employee_id
           JOIN expense_categories c ON c.id = ec.category_id
           WHERE ec.status = 'approved'
           ORDER BY ec.decided_at, ec.id`
        )
        .all() as ApprovedRow[])
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Expense Approvals</h1>
        <p className="text-sm text-gray-500">
          {isHr(user) ? "All pending expense claims." : "Pending expense claims from your direct reports."}
        </p>
      </div>

      <ExpenseTabs active="approvals" showApprovals={true} showAdmin={isHr(user)} />

      {pending.length === 0 ? (
        <div className="card text-sm text-gray-500">Nothing to approve right now.</div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {pending.map((r) => {
            const month = r.expense_date.slice(0, 7);
            const monthTotal = monthCategoryTotal(r.employee_id, r.category_id, month);
            const overLimit = r.monthly_limit !== null && monthTotal > r.monthly_limit;
            return (
              <div key={r.id} className="card space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">{r.employee_name}</p>
                    <p className="text-xs text-gray-500">{r.job_title}</p>
                  </div>
                  <span className="badge-gray">{r.category_name}</span>
                </div>
                <div className="grid grid-cols-3 gap-3 text-sm">
                  <div>
                    <p className="label">Date</p>
                    <p className="whitespace-nowrap">{r.expense_date}</p>
                  </div>
                  <div>
                    <p className="label">Amount</p>
                    <p className="font-medium">{formatRand(r.amount)}</p>
                  </div>
                  <div>
                    <p className="label">Month-to-date</p>
                    <p className={overLimit ? "font-medium text-red-600" : ""}>
                      {formatRand(monthTotal)}
                      {r.monthly_limit !== null && (
                        <span className="text-gray-400"> / {formatRand(r.monthly_limit)}</span>
                      )}
                    </p>
                  </div>
                </div>
                <p className="rounded-lg bg-gray-50 px-3 py-2 text-sm text-gray-600">&ldquo;{r.description}&rdquo;</p>
                <p className="text-xs text-gray-500">
                  Receipt:{" "}
                  {r.receipt_filename ? (
                    <span className="font-mono">{r.receipt_filename}</span>
                  ) : (
                    <span className="text-gray-400">none provided</span>
                  )}
                </p>
                <ClaimDecisionButtons claimId={r.id} />
              </div>
            );
          })}
        </div>
      )}

      {isHr(user) && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Awaiting reimbursement</h2>
          {awaitingReimbursement.length === 0 ? (
            <div className="card text-sm text-gray-500">No approved claims awaiting reimbursement.</div>
          ) : (
            <div className="card overflow-x-auto p-0">
              <table className="w-full">
                <thead className="border-b border-gray-200 bg-gray-50">
                  <tr>
                    <th className="th">Employee</th>
                    <th className="th">Date</th>
                    <th className="th">Category</th>
                    <th className="th">Description</th>
                    <th className="th">Amount</th>
                    <th className="th">Approved</th>
                    <th className="th"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {awaitingReimbursement.map((r) => (
                    <tr key={r.id}>
                      <td className="td whitespace-nowrap">{r.employee_name}</td>
                      <td className="td whitespace-nowrap">{r.expense_date}</td>
                      <td className="td whitespace-nowrap">{r.category_name}</td>
                      <td className="td max-w-xs">{r.description}</td>
                      <td className="td whitespace-nowrap font-medium">{formatRand(r.amount)}</td>
                      <td className="td whitespace-nowrap text-gray-500">{r.decided_at?.slice(0, 10) ?? "—"}</td>
                      <td className="td text-right">
                        <ReimburseButton claimId={r.id} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
