import { NextRequest, NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getApiUser, isHr } from "@/lib/session";

export const dynamic = "force-dynamic";

/** Quote a CSV field when it contains a delimiter, quote or newline. */
function csv(value: string | number | null | undefined): string {
  const s = value === null || value === undefined ? "" : String(value);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

interface Irp5Row {
  employee_number: string;
  first_name: string;
  last_name: string;
  date_of_birth: string | null;
  nationality: string | null;
  work_email: string;
  gross_3601: number;
  paye_4102: number;
  uif_4141: number;
  periods: number;
}

/**
 * GET /api/payroll/exports/irp5?year=YYYY
 *
 * IRP5-style annual tax certificate export (CSV), one row per employee,
 * aggregating payslips from approved/paid runs in the SA tax year ending
 * February YYYY (1 March YYYY-1 → end of February YYYY).
 * SARS source codes: 3601 = gross remuneration, 4102 = PAYE, 4141 = UIF.
 */
export async function GET(req: NextRequest) {
  const user = getApiUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthenticated." }, { status: 401 });
  }
  if (!isHr(user)) {
    return NextResponse.json({ error: "Forbidden: HR/admin only." }, { status: 403 });
  }

  const year = Number(req.nextUrl.searchParams.get("year"));
  if (!Number.isInteger(year) || year < 2000 || year > 2100) {
    return NextResponse.json({ error: "A valid ?year=YYYY is required." }, { status: 400 });
  }

  // SA tax year YYYY runs 1 March (YYYY-1) to end of February YYYY.
  const taxYearStart = `${year - 1}-03-01`;
  const taxYearEnd = `${year}-03-01`; // exclusive

  const db = getDb();
  const rows = db
    .prepare(
      `SELECT e.employee_number, e.first_name, e.last_name, e.date_of_birth, e.nationality, e.work_email,
              SUM(ps.gross_pay)     AS gross_3601,
              SUM(ps.income_tax)    AS paye_4102,
              SUM(ps.uif_employee)  AS uif_4141,
              COUNT(ps.id)          AS periods
       FROM payslips ps
       JOIN payroll_runs pr ON pr.id = ps.payroll_run_id
       JOIN employees e     ON e.id = ps.employee_id
       WHERE pr.status IN ('approved', 'paid')
         AND pr.payment_date >= ? AND pr.payment_date < ?
       GROUP BY e.id
       ORDER BY e.employee_number`
    )
    .all(taxYearStart, taxYearEnd) as Irp5Row[];

  const header = [
    "tax_year",
    "employee_number",
    "last_name",
    "first_name",
    "date_of_birth",
    "nationality",
    "work_email",
    "gross_remuneration_3601",
    "paye_4102",
    "uif_employee_4141",
    "periods",
  ].join(",");

  const body = rows.map((r) =>
    [
      csv(year),
      csv(r.employee_number),
      csv(r.last_name),
      csv(r.first_name),
      csv(r.date_of_birth),
      csv(r.nationality),
      csv(r.work_email),
      csv(r.gross_3601.toFixed(2)),
      csv(r.paye_4102.toFixed(2)),
      csv(r.uif_4141.toFixed(2)),
      csv(r.periods),
    ].join(",")
  );

  logAudit(user.id, "export", "irp5", null, `Tax year ${year}: ${rows.length} employees`);

  return new NextResponse([header, ...body].join("\r\n") + "\r\n", {
    status: 200,
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="irp5-${year}.csv"`,
      "Cache-Control": "no-store",
    },
  });
}
