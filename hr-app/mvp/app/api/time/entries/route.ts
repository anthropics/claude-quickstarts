import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getApiUser } from "@/lib/session";
import { notify } from "@/lib/notify";
import {
  addDays,
  hhmmToMinutes,
  isValidDateString,
  isValidHHMM,
  manualEntryOverlaps,
  todaySql,
} from "@/app/time/_lib/time";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const user = getApiUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = (await req.json().catch(() => null)) as {
    date?: string;
    start_time?: string;
    end_time?: string;
    break_minutes?: number;
    reason?: string;
  } | null;
  if (!body) return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });

  const { date, start_time, end_time } = body;
  const reason = typeof body.reason === "string" ? body.reason.trim() : "";
  const breakMinutes = Number.isInteger(body.break_minutes) ? Number(body.break_minutes) : body.break_minutes === undefined ? 0 : NaN;

  if (!isValidDateString(date)) {
    return NextResponse.json({ error: "date must be a YYYY-MM-DD date." }, { status: 400 });
  }
  const today = todaySql();
  if (date > today) {
    return NextResponse.json({ error: "Cannot add time for a future date." }, { status: 400 });
  }
  if (date < addDays(today, -14)) {
    return NextResponse.json({ error: "Corrections are limited to the last 14 days." }, { status: 400 });
  }
  if (!isValidHHMM(start_time) || !isValidHHMM(end_time)) {
    return NextResponse.json({ error: "Start and end times are required (HH:MM)." }, { status: 400 });
  }
  const durationMinutes = hhmmToMinutes(end_time) - hhmmToMinutes(start_time);
  if (durationMinutes <= 0) {
    return NextResponse.json({ error: "End time must be after start time." }, { status: 400 });
  }
  if (Number.isNaN(breakMinutes) || breakMinutes < 0 || breakMinutes >= durationMinutes) {
    return NextResponse.json({ error: "Break minutes must be 0 or more and shorter than the entry." }, { status: 400 });
  }
  if (!reason) {
    return NextResponse.json({ error: "A reason for the correction is required." }, { status: 400 });
  }

  const db = getDb();

  // Overlap with existing clock events on that date
  const dayEvents = db
    .prepare(
      "SELECT type, timestamp FROM clock_events WHERE employee_id = ? AND date(timestamp) = ? ORDER BY timestamp, id"
    )
    .all(user.id, date) as { type: string; timestamp: string }[];
  if (manualEntryOverlaps(dayEvents, start_time, end_time)) {
    return NextResponse.json(
      { error: "This entry overlaps time you already clocked on that date." },
      { status: 400 }
    );
  }

  const result = db
    .prepare(
      `INSERT INTO manual_time_entries (employee_id, date, start_time, end_time, break_minutes, reason, status, approver_id)
       VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)`
    )
    .run(user.id, date, start_time, end_time, breakMinutes, reason, user.manager_id);
  const id = Number(result.lastInsertRowid);
  logAudit(user.id, "time_entry.create", "manual_time_entry", id, `${date} ${start_time}-${end_time} (break ${breakMinutes}m)`);

  // Notify the manager (HR fallback when there is no manager).
  const reviewerIds = user.manager_id
    ? [user.manager_id]
    : (db.prepare("SELECT id FROM employees WHERE role IN ('hr','admin') AND status = 'active' AND id != ?").all(user.id) as { id: number }[]).map((r) => r.id);
  for (const reviewerId of reviewerIds) {
    notify({
      employeeId: reviewerId,
      type: "time_entry.submitted",
      title: `Timesheet correction from ${user.first_name} ${user.last_name}`,
      body: `${date}, ${start_time}–${end_time}${breakMinutes > 0 ? ` (${breakMinutes} min break)` : ""}. Reason: ${reason}`,
      link: "/time/team",
    });
  }

  return NextResponse.json({ id, status: "pending" }, { status: 201 });
}
