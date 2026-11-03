import Link from "next/link";
import { notFound } from "next/navigation";
import { getDb } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { PayrollRun, Payslip, Employee } from "@/lib/types";
import type { EnginePayslipLine } from "@/app/payroll/_lib/engine";
import PrintButton from "@/app/payroll/_components/PrintButton";

export const dynamic = "force-dynamic";

function fmt(n: number) {
  return new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR", minimumFractionDigits: 2 }).format(n);
}

export default function IndividualPayslipPage({
  params,
}: {
  params: { id: string; empId: string };
}) {
  const user = getCurrentUser();
  const runId = Number(params.id);
  const empId = Number(params.empId);

  // Employees can only see their own payslip; HR can see all
  if (!isHr(user) && user.id !== empId) {
    return (
      <div className="card max-w-md">
        <h1 className="text-lg font-semibold text-red-600">Access Denied</h1>
        <p className="mt-1 text-sm text-gray-600">You can only view your own payslips.</p>
        <Link href="/payroll/my-payslips" className="mt-4 inline-block text-sm font-medium text-brand-600 hover:underline">
          My payslips →
        </Link>
      </div>
    );
  }

  const db = getDb();
  const run = db.prepare("SELECT * FROM payroll_runs WHERE id = ?").get(runId) as PayrollRun | undefined;
  if (!run) notFound();

  const payslip = db
    .prepare("SELECT * FROM payslips WHERE payroll_run_id = ? AND employee_id = ?")
    .get(runId, empId) as Payslip | undefined;
  if (!payslip) notFound();

  const employee = db
    .prepare(
      `SELECT e.*, d.name AS department_name
       FROM employees e
       LEFT JOIN departments d ON d.id = e.department_id
       WHERE e.id = ?`
    )
    .get(empId) as (Employee & { department_name: string | null }) | undefined;
  if (!employee) notFound();

  const lines: EnginePayslipLine[] = JSON.parse(payslip.lines ?? "[]");
  const earningLines = lines.filter((l) => l.type === "earning");
  const deductionLines = lines.filter((l) => l.type === "deduction");
  const infoLines = lines.filter((l) => l.type === "info");

  const backHref = isHr(user) ? `/payroll/${runId}` : "/payroll/my-payslips";
  const backLabel = isHr(user) ? "Back to Pay Run" : "My Payslips";

  return (
    <>
      {/* Print-hide nav breadcrumb */}
      <div className="mb-6 print:hidden">
        <Link href={backHref} className="text-sm font-medium text-brand-600 hover:underline">
          ← {backLabel}
        </Link>
      </div>

      {/* Payslip document */}
      <div className="mx-auto max-w-2xl space-y-6 rounded-xl border border-gray-200 bg-white p-8 shadow-sm print:shadow-none print:border-0 print:p-0">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-gray-200 pb-6">
          <div>
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 font-bold text-white print:hidden">
                H
              </div>
              <span className="text-xl font-bold">HRCore</span>
            </div>
            <p className="mt-1 text-sm text-gray-500">Acme (Pty) Ltd</p>
          </div>
          <div className="text-right">
            <p className="text-sm font-semibold uppercase tracking-wide text-gray-500">Payslip</p>
            <p className="mt-1 text-sm text-gray-700">
              {run.period_start} — {run.period_end}
            </p>
            <p className="text-sm text-gray-500">Payment: {run.payment_date}</p>
          </div>
        </div>

        {/* Employee info */}
        <div className="grid grid-cols-2 gap-4 border-b border-gray-200 pb-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Employee</p>
            <p className="mt-1 text-base font-semibold">
              {employee.first_name} {employee.last_name}
            </p>
            <p className="text-sm text-gray-600">{employee.job_title}</p>
            {employee.department_name && (
              <p className="text-sm text-gray-500">{employee.department_name}</p>
            )}
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Employee Number</p>
            <p className="mt-1 text-sm font-mono font-medium">{employee.employee_number}</p>
            <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-gray-400">Status</p>
            <p className="mt-0.5 text-sm capitalize">
              {run.status === "paid" ? (
                <span className="badge-blue">Paid</span>
              ) : run.status === "approved" ? (
                <span className="badge-green">Approved</span>
              ) : (
                <span className="badge-yellow capitalize">{run.status}</span>
              )}
            </p>
          </div>
        </div>

        {/* Earnings */}
        <div>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">Earnings</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="pb-1.5 text-left font-medium text-gray-500">Description</th>
                <th className="pb-1.5 text-right font-medium text-gray-500">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {earningLines.map((l, i) => (
                <tr key={i}>
                  <td className="py-1.5 text-gray-700">{l.label}</td>
                  <td className="py-1.5 text-right font-mono">{fmt(l.amount)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-gray-200 font-semibold">
                <td className="pt-2">Gross Pay</td>
                <td className="pt-2 text-right font-mono">{fmt(payslip.gross_pay)}</td>
              </tr>
            </tfoot>
          </table>
        </div>

        {/* Deductions */}
        <div>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">Deductions</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="pb-1.5 text-left font-medium text-gray-500">Description</th>
                <th className="pb-1.5 text-right font-medium text-gray-500">Amount</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {deductionLines.map((l, i) => (
                <tr key={i}>
                  <td className="py-1.5 text-gray-700">{l.label}</td>
                  <td className="py-1.5 text-right font-mono text-red-600">({fmt(l.amount)})</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-gray-200 font-semibold">
                <td className="pt-2">Total Deductions</td>
                <td className="pt-2 text-right font-mono text-red-600">({fmt(payslip.total_deductions)})</td>
              </tr>
            </tfoot>
          </table>
        </div>

        {/* Info lines (e.g. medical scheme fees tax credit) */}
        {infoLines.length > 0 && (
          <div className="rounded-lg bg-gray-50 px-4 py-3 text-sm text-gray-600">
            {infoLines.map((l, i) => (
              <div key={i} className="flex items-center justify-between gap-4">
                <span>Note: {l.label}</span>
                <span className="font-mono">{fmt(l.amount)}</span>
              </div>
            ))}
          </div>
        )}

        {/* Net pay */}
        <div className="rounded-lg bg-brand-600 px-5 py-4 text-white">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold uppercase tracking-wide opacity-80">Net Pay</span>
            <span className="text-2xl font-bold font-mono">{fmt(payslip.net_pay)}</span>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 pt-4 text-center text-xs text-gray-400">
          This payslip is computer-generated and does not require a signature. · Acme (Pty) Ltd
        </div>
      </div>

      {/* Print button */}
      <div className="mx-auto mt-4 max-w-2xl text-right print:hidden">
        <PrintButton />
      </div>
    </>
  );
}
