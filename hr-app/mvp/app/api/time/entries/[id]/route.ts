import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getApiUser, isHr } from "@/lib/session";
import { notify } from "@/lib/notify";
import {
  hhmmToMinutes,
  manualEntryOverlaps,
  minutesToHHMM,
} from "@/app/time/_lib/time";

export const dynamic = "force-dynamic";

interface ManualTimeEntry {
  id: number;
  employee_id: number;
  date: string;
  start_time: string;
  end_time: string;
  break_minutes: number;
  reason: string;
  status: "pending" | "approved" | "rejected";
  approver_id: number | null;
  decided_at: string | null;
}

export async function PATCH(req: Request, { params }: { params: { id: string } }) {
  const user = getApiUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const id = Number(params.id);
  if (!Number.isInteger(id)) {
    return NextResponse.json({ error: "Invalid entry id." }, { status: 400 });
  }

  const body = (await req.json().catch(() => null)) as { action?: string } | null;
  const action = body?.action;
  if (action !== "approve" && action !== "reject") {
    return NextResponse.json({ error: "action must be 'approve' or 'reject'." }, { status: 400 });
  }

  const db = getDb();
  const entry = db
    .prepare(
      `SELECT m.*, e.manager_id AS employee_manager_id
       FROM manual_time_entries m JOIN employees e ON e.id = m.employee_id
       WHERE m.id = ?`
    )
    .get(id) as (ManualTimeEntry & { employee_manager_id: number | null }) | undefined;

  if (!entry) {
    return NextResponse.json({ error: "Time entry not found." }, { status: 404 });
  }
  if (!isHr(user) && entry.employee_manager_id !== user.id) {
    return NextResponse.json({ error: "You may only review corrections of your direct reports." }, { status: 403 });
  }
  if (entry.status !== "pending") {
    return NextResponse.json(
      { error: `Only pending corrections can be reviewed (current status: ${entry.status}).` },
      { status: 400 }
    );
  }

  if (action === "approve") {
    // Re-check overlap: clock events may have changed since submission.
    const dayEvents = db
      .prepare(
        "SELECT type, timestamp FROM clock_events WHERE employee_id = ? AND date(timestamp) = ? ORDER BY timestamp, id"
      )
      .all(entry.employee_id, entry.date) as { type: string; timestamp: string }[];
    if (manualEntryOverlaps(dayEvents, entry.start_time, entry.end_time)) {
      return NextResponse.json(
        { error: "This entry now overlaps existing clock events for that date and cannot be approved." },
        { status: 400 }
      );
    }

    const insert = db.prepare(
      "INSERT INTO clock_events (employee_id, type, timestamp, method) VALUES (?, ?, ?, 'manual')"
    );
    const ts = (hhmm: string) => `${entry.date} ${hhmm}:00`;

    db.transaction(() => {
      insert.run(entry.employee_id, "clock_in", ts(entry.start_time));
      if (entry.break_minutes > 0) {
        // Place the break in the middle of the entry.
        const mid = (hhmmToMinutes(entry.start_time) + hhmmToMinutes(entry.end_time)) / 2;
        const breakStart = minutesToHHMM(mid - entry.break_minutes / 2);
        const breakEnd = minutesToHHMM(mid + entry.break_minutes / 2);
        insert.run(entry.employee_id, "break_start", ts(breakStart));
        insert.run(entry.employee_id, "break_end", ts(breakEnd));
      }
      insert.run(entry.employee_id, "clock_out", ts(entry.end_time));
      db.prepare(
        "UPDATE manual_time_entries SET status = 'approved', approver_id = ?, decided_at = datetime('now') WHERE id = ?"
      ).run(user.id, id);
    })();
  } else {
    db.prepare(
      "UPDATE manual_time_entries SET status = 'rejected', approver_id = ?, decided_at = datetime('now') WHERE id = ?"
    ).run(user.id, id);
  }

  const status = action === "approve" ? "approved" : "rejected";
  logAudit(user.id, `time_entry.${action}`, "manual_time_entry", id, `${entry.date} ${entry.start_time}-${entry.end_time} for employee ${entry.employee_id}`);

  notify({
    employeeId: entry.employee_id,
    type: `time_entry.${status}`,
    title: `Your timesheet correction was ${status}`,
    body: `${entry.date}, ${entry.start_time}–${entry.end_time}${entry.break_minutes > 0 ? ` (${entry.break_minutes} min break)` : ""} — ${status} by ${user.first_name} ${user.last_name}.`,
    link: "/time",
  });

  return NextResponse.json({ ok: true, status });
}
