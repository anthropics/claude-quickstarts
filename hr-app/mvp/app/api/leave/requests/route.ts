import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser } from "@/lib/session";
import { notify } from "@/lib/notify";
import type { LeaveType } from "@/lib/types";
import { computeLeaveDays, formatDays, getBalance, getHolidaySet, isIsoDate } from "@/app/leave/_lib/leave";

export async function POST(request: Request) {
  const user = getCurrentUser();
  const db = getDb();

  let body: {
    leave_type_id?: number;
    start_date?: string;
    end_date?: string;
    notes?: string;
    start_half?: boolean;
    end_half?: boolean;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const { leave_type_id, start_date, end_date } = body;
  const notes = typeof body.notes === "string" && body.notes.trim() ? body.notes.trim() : null;

  if (!isIsoDate(start_date) || !isIsoDate(end_date)) {
    return NextResponse.json({ error: "Start and end dates are required (YYYY-MM-DD)." }, { status: 400 });
  }
  if (end_date < start_date) {
    return NextResponse.json({ error: "End date cannot be before start date." }, { status: 400 });
  }

  // Half-day flags. For a single-day request there is only one "half day"
  // choice — normalise it onto start_half.
  const singleDay = start_date === end_date;
  let startHalf = body.start_half === true;
  let endHalf = body.end_half === true;
  if (singleDay && (startHalf || endHalf)) {
    startHalf = true;
    endHalf = false;
  }

  const leaveType = db.prepare("SELECT * FROM leave_types WHERE id = ?").get(leave_type_id) as LeaveType | undefined;
  if (!leaveType) {
    return NextResponse.json({ error: "Unknown leave type." }, { status: 400 });
  }

  // Probation restriction
  const today = new Date().toISOString().slice(0, 10);
  if (leaveType.probation_restricted === 1 && user.probation_end_date && user.probation_end_date > today) {
    return NextResponse.json(
      { error: `${leaveType.name} is not available during probation (ends ${user.probation_end_date}).` },
      { status: 400 }
    );
  }

  // Overlap with existing pending/approved requests
  const overlap = db
    .prepare(
      `SELECT id, start_date, end_date FROM leave_requests
       WHERE employee_id = ? AND status IN ('pending', 'approved')
         AND start_date <= ? AND end_date >= ?
       LIMIT 1`
    )
    .get(user.id, end_date, start_date) as { id: number; start_date: string; end_date: string } | undefined;
  if (overlap) {
    return NextResponse.json(
      { error: `This overlaps an existing request (${overlap.start_date} to ${overlap.end_date}).` },
      { status: 400 }
    );
  }

  // Working days (server-side), with half-day flags applied
  const days = computeLeaveDays(start_date, end_date, getHolidaySet(), startHalf, endHalf);
  if (days <= 0) {
    return NextResponse.json(
      { error: "The selected range contains no working days (weekends / public holidays only)." },
      { status: 400 }
    );
  }

  // Balance check — single source of truth (accrual-aware getBalance)
  if (leaveType.negative_balance_allowed === 0) {
    const year = Number(start_date.slice(0, 4));
    const balance = getBalance(user.id, leaveType.id, year, db);
    const remaining = balance?.available ?? 0;
    if (days > remaining) {
      return NextResponse.json(
        { error: `Insufficient balance: ${formatDays(remaining)} day(s) of ${leaveType.name} available, ${formatDays(days)} requested.` },
        { status: 400 }
      );
    }
  }

  const result = db
    .prepare(
      `INSERT INTO leave_requests
         (employee_id, leave_type_id, start_date, end_date, days, notes, status, approver_id, start_half, end_half)
       VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)`
    )
    .run(user.id, leaveType.id, start_date, end_date, days, notes, user.manager_id, startHalf ? 1 : 0, endHalf ? 1 : 0);

  const id = Number(result.lastInsertRowid);
  logAudit(user.id, "create", "leave_request", id, `${leaveType.code} ${start_date}..${end_date} (${days}d)`);

  // Notify the approver: the manager, or HR as fallback for employees without one.
  const approverIds = user.manager_id
    ? [user.manager_id]
    : (db.prepare("SELECT id FROM employees WHERE role IN ('hr','admin') AND status = 'active' AND id != ?").all(user.id) as { id: number }[]).map((r) => r.id);
  const range = singleDay ? start_date : `${start_date} to ${end_date}`;
  for (const approverId of approverIds) {
    notify({
      employeeId: approverId,
      type: "leave.submitted",
      title: `Leave request from ${user.first_name} ${user.last_name}`,
      body: `${leaveType.name}: ${range} (${formatDays(days)} day${days === 1 ? "" : "s"}).${notes ? ` Note: ${notes}` : ""}`,
      link: "/leave/approvals",
    });
  }

  return NextResponse.json({ id, days, status: "pending" }, { status: 201 });
}
