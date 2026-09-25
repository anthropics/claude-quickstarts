import { NextRequest, NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getApiUser, isHr } from "@/lib/session";
import { notify } from "@/lib/notify";
import type { PayrollRun } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
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

  let body: { action: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON." }, { status: 400 });
  }

  const { action } = body;
  if (!["approve", "mark_paid", "cancel"].includes(action)) {
    return NextResponse.json({ error: "action must be one of: approve, mark_paid, cancel." }, { status: 400 });
  }

  const db = getDb();
  const run = db.prepare("SELECT * FROM payroll_runs WHERE id = ?").get(runId) as PayrollRun | undefined;
  if (!run) {
    return NextResponse.json({ error: "Payroll run not found." }, { status: 404 });
  }

  // Enforce valid status transitions
  if (action === "approve" && run.status !== "draft") {
    return NextResponse.json({ error: `Cannot approve a run with status '${run.status}'. Only draft runs can be approved.` }, { status: 400 });
  }
  if (action === "mark_paid" && run.status !== "approved") {
    return NextResponse.json({ error: `Cannot mark as paid a run with status '${run.status}'. Only approved runs can be marked paid.` }, { status: 400 });
  }
  if (action === "cancel" && (run.status === "paid" || run.status === "cancelled")) {
    return NextResponse.json({ error: `Cannot cancel a run with status '${run.status}'.` }, { status: 400 });
  }

  let newStatus: string;
  if (action === "approve") newStatus = "approved";
  else if (action === "mark_paid") newStatus = "paid";
  else newStatus = "cancelled";

  if (action === "approve") {
    db.prepare(
      "UPDATE payroll_runs SET status = ?, approved_by = ?, approved_at = datetime('now') WHERE id = ?"
    ).run(newStatus, user.id, runId);
  } else {
    db.prepare("UPDATE payroll_runs SET status = ? WHERE id = ?").run(newStatus, runId);
  }

  logAudit(user.id, action, "payroll_run", runId, `Status changed to ${newStatus}`);

  // Notify every employee in the run when their payslip becomes available /
  // their salary is paid.
  if (action === "approve" || action === "mark_paid") {
    const period = `${run.period_start} – ${run.period_end}`;
    const employeeIds = (
      db.prepare("SELECT employee_id FROM payslips WHERE payroll_run_id = ?").all(runId) as {
        employee_id: number;
      }[]
    ).map((r) => r.employee_id);

    for (const empId of employeeIds) {
      if (action === "approve") {
        notify({
          employeeId: empId,
          type: "payroll.payslip",
          title: `Your payslip for ${period} is ready`,
          body: `Your payslip for the pay period ${period} has been approved and is now available. Payment is scheduled for ${run.payment_date}.`,
          link: `/payroll/${runId}/payslips/${empId}`,
        });
      } else {
        notify({
          employeeId: empId,
          type: "payroll.paid",
          title: "Salary payment processed",
          body: `Your salary for the pay period ${period} has been paid (payment date ${run.payment_date}).`,
          link: `/payroll/${runId}/payslips/${empId}`,
        });
      }
    }
  }

  return NextResponse.json({ id: runId, status: newStatus });
}
