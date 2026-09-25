import Link from "next/link";
import { getDb } from "@/lib/db";
import { getCurrentUser } from "@/lib/session";

export const dynamic = "force-dynamic";

interface MyPayslipRow {
  payroll_run_id: number;
  period_start: string;
  period_end: string;
  payment_date: string;
  run_status: string;
  gross_pay: number;
  net_pay: number;
}

function fmt(n: number) {
  return new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR", maximumFractionDigits: 2 }).format(n);
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

export default function MyPayslipsPage() {
  const user = getCurrentUser();
  const db = getDb();

  // Only fetch payslips for the current user
  const payslips = db
    .prepare(
      `SELECT ps.payroll_run_id, pr.period_start, pr.period_end, pr.payment_date,
              pr.status AS run_status, ps.gross_pay, ps.net_pay
       FROM payslips ps
       JOIN payroll_runs pr ON pr.id = ps.payroll_run_id
       WHERE ps.employee_id = ?
       ORDER BY pr.period_start DESC`
    )
    .all(user.id) as MyPayslipRow[];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">My Payslips</h1>
        <p className="text-sm text-gray-500">
          Your payslip history across all payroll runs.
        </p>
      </div>

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="border-b border-gray-200 bg-gray-50">
            <tr>
              <th className="th">Pay Period</th>
              <th className="th">Payment Date</th>
              <th className="th text-right">Gross Pay</th>
              <th className="th text-right">Net Pay</th>
              <th className="th">Status</th>
              <th className="th"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {payslips.length === 0 && (
              <tr>
                <td className="td text-gray-500" colSpan={6}>
                  No payslips found. Your payslips will appear here once a payroll run is processed.
                </td>
              </tr>
            )}
            {payslips.map((p) => (
              <tr key={p.payroll_run_id} className="hover:bg-gray-50">
                <td className="td font-medium">
                  {p.period_start} → {p.period_end}
                </td>
                <td className="td">{p.payment_date}</td>
                <td className="td text-right font-mono">{fmt(p.gross_pay)}</td>
                <td className="td text-right font-mono font-semibold">{fmt(p.net_pay)}</td>
                <td className="td">{statusBadge(p.run_status)}</td>
                <td className="td text-right">
                  <Link
                    href={`/payroll/${p.payroll_run_id}/payslips/${user.id}`}
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
