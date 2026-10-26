import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getApiUser, isHr } from "@/lib/session";
import type { PayrollRun } from "@/lib/types";

export const dynamic = "force-dynamic";

interface EftRow {
  employee_number: string;
  name: string;
  net_pay: number;
}

/**
 * GET /api/payroll/runs/[id]/eft
 *
 * Fixed-format EFT bank payment file for an approved or paid run. One line per
 * employee: employee number, name, net pay in cents, payment date, reference
 * SAL-<runId>-<employeeNumber>. Names are uppercased and stripped of commas so
 * the file stays strictly comma-delimited.
 */
export async function GET(_req: Request, { params }: { params: { id: string } }) {
  const user = getApiUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthenticated." }, { status: 401 });
  }
  if (!isHr(user)) {
    return NextResponse.json({ error: "Forbidden: HR/admin only." }, { status: 403 });
  }

  const runId = Number(params.id);
  if (isNaN(runId)) {
    return NextResponse.json({ error: "Invalid run ID." }, { status: 400 });
  }

  const db = getDb();
  const run = db.prepare("SELECT * FROM payroll_runs WHERE id = ?").get(runId) as PayrollRun | undefined;
  if (!run) {
    return NextResponse.json({ error: "Payroll run not found." }, { status: 404 });
  }
  if (run.status !== "approved" && run.status !== "paid") {
    return NextResponse.json(
      { error: `EFT file is only available for approved or paid runs (status: '${run.status}').` },
      { status: 400 }
    );
  }

  const rows = db
    .prepare(
      `SELECT e.employee_number, e.first_name || ' ' || e.last_name AS name, ps.net_pay
       FROM payslips ps
       JOIN employees e ON e.id = ps.employee_id
       WHERE ps.payroll_run_id = ?
       ORDER BY e.employee_number`
    )
    .all(runId) as EftRow[];

  const lines = rows.map((r) => {
    const name = r.name.toUpperCase().replace(/[,\r\n]/g, " ").trim();
    const netCents = Math.round(r.net_pay * 100);
    return [r.employee_number, name, netCents, run.payment_date, `SAL-${runId}-${r.employee_number}`].join(",");
  });

  logAudit(user.id, "export", "payroll_run_eft", runId, `${rows.length} payment lines`);

  return new NextResponse(lines.join("\r\n") + "\r\n", {
    status: 200,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Content-Disposition": `attachment; filename="eft-run-${runId}-${run.payment_date}.txt"`,
      "Cache-Control": "no-store",
    },
  });
}
