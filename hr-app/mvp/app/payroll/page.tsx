import Link from "next/link";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import ExportsCard from "./_components/ExportsCard";

export const dynamic = "force-dynamic";

interface RunRow {
  id: number;
  period_start: string;
  period_end: string;
  payment_date: string;
  status: string;
  notes: string | null;
  emp_count: number;
  total_gross: number;
  total_net: number;
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
  return new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR", maximumFractionDigits: 0 }).format(n);
}

export default function PayrollPage() {
  const user = getCurrentUser();

  if (!isHr(user)) {
    return (
      <div className="card max-w-md">
        <h1 className="text-lg font-semibold text-red-600">Access Denied</h1>
        <p className="mt-1 text-sm text-gray-600">
          Payroll runs are only accessible to HR administrators. Contact your HR team for payslip queries.
        </p>
        <Link href="/payroll/my-payslips" className="mt-4 inline-block text-sm font-medium text-brand-600 hover:underline">
          View your payslips →
        </Link>
      </div>
    );
  }

  const db = getDb();
  const runs = db
    .prepare(
      `SELECT pr.id, pr.period_start, pr.period_end, pr.payment_date, pr.status, pr.notes,
              COUNT(ps.id) AS emp_count,
              COALESCE(SUM(ps.gross_pay), 0) AS total_gross,
              COALESCE(SUM(ps.net_pay), 0) AS total_net
       FROM payroll_runs pr
       LEFT JOIN payslips ps ON ps.payroll_run_id = pr.id
       GROUP BY pr.id
       ORDER BY pr.period_start DESC`
    )
    .all() as RunRow[];

  // Tax years with exportable data (SA tax year ends end-of-February): a
  // payment in Mar–Dec YYYY falls in tax year YYYY+1; Jan–Feb in tax year YYYY.
  const taxYears = new Set<number>();
  const paymentDates = db
    .prepare("SELECT payment_date FROM payroll_runs WHERE status IN ('approved', 'paid')")
    .all() as { payment_date: string }[];
  for (const { payment_date } of paymentDates) {
    const y = Number(payment_date.slice(0, 4));
    const m = Number(payment_date.slice(5, 7));
    if (y) taxYears.add(m >= 3 ? y + 1 : y);
  }
  if (taxYears.size === 0) {
    const now = new Date();
    taxYears.add(now.getMonth() + 1 >= 3 ? now.getFullYear() + 1 : now.getFullYear());
  }
  const exportYears = Array.from(taxYears).sort((a, b) => b - a);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Payroll</h1>
          <p className="text-sm text-gray-500">Manage and approve payroll runs.</p>
        </div>
        <Link href="/payroll/new" className="btn-primary">
          + New Pay Run
        </Link>
      </div>

      <div className="card overflow-x-auto p-0">
        <table className="w-full">
          <thead className="border-b border-gray-200 bg-gray-50">
            <tr>
              <th className="th">Period</th>
              <th className="th">Payment Date</th>
              <th className="th text-right">Employees</th>
              <th className="th text-right">Total Gross</th>
              <th className="th text-right">Total Net</th>
              <th className="th">Status</th>
              <th className="th"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {runs.length === 0 && (
              <tr>
                <td className="td text-gray-500" colSpan={7}>
                  No payroll runs yet. Create your first pay run above.
                </td>
              </tr>
            )}
            {runs.map((r) => (
              <tr key={r.id} className="hover:bg-gray-50">
                <td className="td font-medium">
                  {r.period_start} → {r.period_end}
                </td>
                <td className="td">{r.payment_date}</td>
                <td className="td text-right">{r.emp_count}</td>
                <td className="td text-right font-mono">{fmt(r.total_gross)}</td>
                <td className="td text-right font-mono">{fmt(r.total_net)}</td>
                <td className="td">{statusBadge(r.status)}</td>
                <td className="td text-right">
                  <Link href={`/payroll/${r.id}`} className="text-sm font-medium text-brand-600 hover:underline">
                    View →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <ExportsCard years={exportYears} />
    </div>
  );
}
