import { NextRequest, NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getApiUser, isHr } from "@/lib/session";
import { calculatePayslip } from "@/app/payroll/_lib/engine";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const user = getApiUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthenticated." }, { status: 401 });
  }
  if (!isHr(user)) {
    return NextResponse.json({ error: "Forbidden: HR/admin only." }, { status: 403 });
  }

  let body: { period_start: string; period_end: string; payment_date: string; notes?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON." }, { status: 400 });
  }

  const { period_start, period_end, payment_date, notes } = body;
  if (!period_start || !period_end || !payment_date) {
    return NextResponse.json({ error: "period_start, period_end and payment_date are required." }, { status: 400 });
  }

  const db = getDb();

  // Create the payroll run
  const runResult = db
    .prepare(
      `INSERT INTO payroll_runs (period_start, period_end, payment_date, status, notes, created_by)
       VALUES (?, ?, ?, 'draft', ?, ?)`
    )
    .run(period_start, period_end, payment_date, notes ?? null, user.id);
  const runId = runResult.lastInsertRowid as number;

  // Fetch all active employees and their earnings/deductions
  const employees = db
    .prepare("SELECT id, medical_aid_members FROM employees WHERE status = 'active'")
    .all() as { id: number; medical_aid_members: number }[];

  const insertPayslip = db.prepare(`
    INSERT INTO payslips (payroll_run_id, employee_id, gross_pay, income_tax, uif_employee, total_deductions, net_pay, lines)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `);

  const insertMany = db.transaction(() => {
    for (const emp of employees) {
      const earnings = db
        .prepare(
          `SELECT ec.name, ec.taxable, ee.amount
           FROM employee_earnings ee
           JOIN earnings_codes ec ON ec.id = ee.earnings_code_id
           WHERE ee.employee_id = ?`
        )
        .all(emp.id) as { name: string; taxable: number; amount: number }[];

      const deductions = db
        .prepare(
          `SELECT dc.name, dc.code, dc.calc_type, dc.rate, dc.pre_tax, dc.statutory, ed.override_amount
           FROM employee_deductions ed
           JOIN deduction_codes dc ON dc.id = ed.deduction_code_id
           WHERE ed.employee_id = ? AND ed.active = 1`
        )
        .all(emp.id) as {
        name: string;
        code: string;
        calc_type: "percentage" | "fixed";
        rate: number;
        pre_tax: number;
        statutory: number;
        override_amount: number | null;
      }[];

      const result = calculatePayslip(earnings, deductions, emp.medical_aid_members ?? 0);

      insertPayslip.run(
        runId,
        emp.id,
        result.gross,
        result.incomeTax,
        result.uif,
        result.totalDeductions,
        result.net,
        JSON.stringify(result.lines)
      );
    }
  });

  insertMany();

  logAudit(user.id, "create", "payroll_run", runId, `Period: ${period_start} to ${period_end}`);

  return NextResponse.json({ id: runId }, { status: 201 });
}
