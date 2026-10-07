import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import { notify } from "@/lib/notify";
import type { Timesheet } from "@/lib/types";
import { nowSql } from "@/app/time/_lib/time";

export const dynamic = "force-dynamic";

export async function PATCH(req: Request, { params }: { params: { id: string } }) {
  const user = getCurrentUser();
  const id = Number(params.id);
  if (!Number.isInteger(id)) {
    return NextResponse.json({ error: "Invalid timesheet id." }, { status: 400 });
  }

  const body = (await req.json().catch(() => null)) as { action?: string } | null;
  const action = body?.action;
  if (action !== "approve" && action !== "reject") {
    return NextResponse.json({ error: "action must be 'approve' or 'reject'." }, { status: 400 });
  }

  const db = getDb();
  const timesheet = db
    .prepare(
      `SELECT t.*, e.manager_id AS employee_manager_id
       FROM timesheets t JOIN employees e ON e.id = t.employee_id
       WHERE t.id = ?`
    )
    .get(id) as (Timesheet & { employee_manager_id: number | null }) | undefined;

  if (!timesheet) {
    return NextResponse.json({ error: "Timesheet not found." }, { status: 404 });
  }
  if (!isHr(user) && timesheet.employee_manager_id !== user.id) {
    return NextResponse.json({ error: "You may only review timesheets of your direct reports." }, { status: 403 });
  }
  if (timesheet.status !== "submitted") {
    return NextResponse.json(
      { error: `Only submitted timesheets can be reviewed (current status: ${timesheet.status}).` },
      { status: 400 }
    );
  }

  const status = action === "approve" ? "approved" : "rejected";
  db.prepare("UPDATE timesheets SET status = ?, decided_at = ? WHERE id = ?").run(status, nowSql(), id);
  logAudit(user.id, `timesheet.${action}`, "timesheet", id, `week ${timesheet.period_start} for employee ${timesheet.employee_id}`);

  notify({
    employeeId: timesheet.employee_id,
    type: `timesheet.${status}`,
    title: `Your timesheet was ${status}`,
    body: `Week ${timesheet.period_start} – ${timesheet.period_end} was ${status} by ${user.first_name} ${user.last_name}.`,
    link: `/time?week=${timesheet.period_start}`,
  });

  return NextResponse.json({ ok: true, status });
}
