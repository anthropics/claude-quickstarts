import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser } from "@/lib/session";
import { notify } from "@/lib/notify";
import type { Timesheet } from "@/lib/types";
import {
  STANDARD_WEEK_MINUTES,
  addDays,
  isValidDateString,
  mondayOf,
  nowSql,
  todaySql,
  workedMinutes,
} from "@/app/time/_lib/time";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const user = getCurrentUser();
  const body = (await req.json().catch(() => null)) as { period_start?: string } | null;
  const periodStart = body?.period_start;

  if (!isValidDateString(periodStart)) {
    return NextResponse.json({ error: "period_start must be a YYYY-MM-DD date." }, { status: 400 });
  }
  if (mondayOf(periodStart) !== periodStart) {
    return NextResponse.json({ error: "period_start must be a Monday." }, { status: 400 });
  }
  if (periodStart > mondayOf(todaySql())) {
    return NextResponse.json({ error: "Cannot submit a timesheet for a future week." }, { status: 400 });
  }

  const periodEnd = addDays(periodStart, 6);
  const db = getDb();

  const existing = db
    .prepare("SELECT * FROM timesheets WHERE employee_id = ? AND period_start = ?")
    .get(user.id, periodStart) as Timesheet | undefined;
  if (existing && existing.status !== "draft" && existing.status !== "rejected") {
    return NextResponse.json(
      { error: `Timesheet for this week is already ${existing.status}.` },
      { status: 400 }
    );
  }

  // Freeze totals from completed clock pairs in the period (open intervals excluded).
  const events = db
    .prepare(
      `SELECT type, timestamp FROM clock_events
       WHERE employee_id = ? AND date(timestamp) BETWEEN ? AND ?
       ORDER BY timestamp, id`
    )
    .all(user.id, periodStart, periodEnd) as { type: string; timestamp: string }[];

  const byDay = new Map<string, { type: string; timestamp: string }[]>();
  for (const e of events) {
    const day = e.timestamp.slice(0, 10);
    const list = byDay.get(day) ?? [];
    list.push(e);
    byDay.set(day, list);
  }
  let totalMinutes = 0;
  byDay.forEach((dayEvents) => {
    totalMinutes += workedMinutes(dayEvents);
  });
  const overtimeMinutes = Math.max(0, totalMinutes - STANDARD_WEEK_MINUTES);

  let id: number;
  if (existing) {
    db.prepare(
      `UPDATE timesheets
       SET status = 'submitted', total_minutes = ?, overtime_minutes = ?, submitted_at = ?, decided_at = NULL
       WHERE id = ?`
    ).run(totalMinutes, overtimeMinutes, nowSql(), existing.id);
    id = existing.id;
  } else {
    const result = db
      .prepare(
        `INSERT INTO timesheets (employee_id, period_start, period_end, status, total_minutes, overtime_minutes, submitted_at)
         VALUES (?, ?, ?, 'submitted', ?, ?, ?)`
      )
      .run(user.id, periodStart, periodEnd, totalMinutes, overtimeMinutes, nowSql());
    id = Number(result.lastInsertRowid);
  }

  logAudit(
    user.id,
    "timesheet.submit",
    "timesheet",
    id,
    `week ${periodStart}: ${totalMinutes} min (${overtimeMinutes} overtime)`
  );

  // Notify the manager (or HR when there is no manager).
  const reviewerIds = user.manager_id
    ? [user.manager_id]
    : (db.prepare("SELECT id FROM employees WHERE role IN ('hr','admin') AND status = 'active' AND id != ?").all(user.id) as { id: number }[]).map((r) => r.id);
  for (const reviewerId of reviewerIds) {
    notify({
      employeeId: reviewerId,
      type: "timesheet.submitted",
      title: `Timesheet submitted by ${user.first_name} ${user.last_name}`,
      body: `Week ${periodStart} – ${periodEnd}: ${Math.floor(totalMinutes / 60)}h ${totalMinutes % 60}m total${overtimeMinutes > 0 ? `, ${Math.floor(overtimeMinutes / 60)}h ${overtimeMinutes % 60}m overtime` : ""}.`,
      link: "/time/team",
    });
  }

  return NextResponse.json({ ok: true, id, total_minutes: totalMinutes, overtime_minutes: overtimeMinutes });
}
