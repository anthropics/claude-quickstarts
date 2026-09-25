import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { PayrollRun } from "@/lib/types";
import RunActions from "../_components/RunActions";

export const dynamic = "force-dynamic";

interface PayslipRow {
  id: number;
  employee_id: number;
  name: string;
  department: string | null;
  gross_pay: number;
  total_deductions: number;
  net_pay: number;
}

function statusBadge(status: string) {
  switch (status) {
    case "draft":
      return <span className="badge-yellow capitalize">{status}</span>;
    case "approved":
      return <span className="badge-green capitalize">{status}</span>;
    case "paid":
      return <span className="badge-blue capitalize">{status}</span>;
    case "cancelled":
      return <span className="badge-gray capitalize">{status}</span>;
    default:
      return <span className="badge-gray capitalize">{status}</span>;
  }
}

function fmt(n: number) {
  return new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR", maximumFractionDigits: 2 }).format(n);
}

export default function PayRunDetailPage({ params }: { params: { id: string } }) {
  const user = getCurrentUser();

  if (!isHr(user)) {
    return (
      <div className="card max-w-md">
        <h1 className="text-lg font-semibold text-red-600">Access Denied</h1>
        <p className="mt-1 text-sm text-gray-600">Payroll run details are only accessible to HR administrators.</p>
        <Link href="/payroll/my-payslips" className="mt-4 inline-block text-sm font-medium text-brand-600 hover:underline">
          View your payslips →
        </Link>
      </div>
    );
  }

  const db = getDb();
  const runId = Number(params.id);
  const run = db.prepare("SELECT * FROM payroll_runs WHERE id = ?").get(runId) as PayrollRun | undefined;
  if (!run) notFound();

  const payslips = db
    .prepare(
      `SELECT ps.id, ps.employee_id,
              e.first_name || ' ' || e.last_name AS name,
              d.name AS department,
              ps.gross_pay, ps.total_deductions, ps.net_pay
       FROM payslips ps
       JOIN employees e ON e.id = ps.employee_id
       LEFT JOIN departments d ON d.id = e.department_id
       WHERE ps.payroll_run_id = ?
       ORDER BY e.last_name, e.first_name`
    )
    .all(runId) as PayslipRow[];

  const totalGross = payslips.reduce((s, p) => s + p.gross_pay, 0);
  const totalNet = payslips.reduce((s, p) => s + p.net_pay, 0);
  const totalDed = payslips.reduce((s, p) => s + p.total_deductions, 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-1 flex items-center gap-2">
            <Link href="/payroll" className="text-sm text-gray-500 hover:underline">
              Payroll
            </Link>
            <span className="text-gray-400">/</span>
            <span className="text-sm text-gray-700">
              {run.period_start} → {run.period_end}
            </span>
          </div>
          <h1 className="text-2xl font-bold">Pay Run</h1>
          <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-gray-500">
            <span>Payment date: {run.payment_date}</span>
            <span>·</span>
            {statusBadge(run.status)}
          </div>
          {run.notes && <p className="mt-1 text-sm text-gray-500">{run.notes}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {(run.status === "approved" || run.status === "paid") && (
            <a href={`/api/payroll/runs/${run.id}/eft`} className="btn-secondary" download>
              Download EFT file
            </a>
          )}
          <RunActions runId={run.id} status={run.status} />
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Employees</p>
          <p className="mt-1 text-3xl font-bold">{payslips.length}</p>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Total Gross</p>
          <p className="mt-1 text-2xl font-bold font-mono">{fmt(totalGross)}</p>
        </div>
        <div className="card">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Total Net</p>
          <p className="mt-1 text-2xl font-bold font-mono">{fmt(totalNet)}</p>
        </div>
      </div>

      {/* Payslips table */}
      <div className="card overflow-x-auto p-0">
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
          <h2 className="font-semibold">Payslips</h2>
          <span className="text-sm text-gray-500">Total deductions: {fmt(totalDed)}</span>
        </div>
        <table className="w-full">
          <thead className="border-b border-gray-200 bg-gray-50">
            <tr>
              <th className="th">Employee</th>
              <th className="th">Department</th>
              <th className="th text-right">Gross Pay</th>
              <th className="th text-right">Deductions</th>
              <th className="th text-right">Net Pay</th>
              <th className="th"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {payslips.length === 0 && (
              <tr>
                <td className="td text-gray-500" colSpan={6}>
                  No payslips found.
                </td>
              </tr>
            )}
            {payslips.map((p) => (
              <tr key={p.id} className="hover:bg-gray-50">
                <td className="td font-medium">{p.name}</td>
                <td className="td text-gray-500">{p.department ?? "—"}</td>
                <td className="td text-right font-mono">{fmt(p.gross_pay)}</td>
                <td className="td text-right font-mono text-red-600">({fmt(p.total_deductions)})</td>
                <td className="td text-right font-mono font-semibold">{fmt(p.net_pay)}</td>
                <td className="td text-right">
                  <Link
                    href={`/payroll/${runId}/payslips/${p.employee_id}`}
                    className="text-sm font-medium text-brand-600 hover:underline"
                  >
                    View →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
