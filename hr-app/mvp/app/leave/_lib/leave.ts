import type DatabaseType from "better-sqlite3";
import { getDb } from "@/lib/db";
import type { LeaveType } from "@/lib/types";

/** leave_types row including the accrual columns added in migration 002. */
export interface LeaveTypeWithAccrual extends LeaveType {
  accrual_method: "annual" | "monthly";
  max_carry_over_days: number;
}

/** ISO date string YYYY-MM-DD validation. */
export function isIsoDate(s: unknown): s is string {
  return typeof s === "string" && /^\d{4}-\d{2}-\d{2}$/.test(s) && !Number.isNaN(Date.parse(s));
}

/** All public holiday dates as a Set of YYYY-MM-DD strings. */
export function getHolidaySet(): Set<string> {
  const rows = getDb().prepare("SELECT date FROM public_holidays").all() as { date: string }[];
  return new Set(rows.map((r) => r.date));
}

/**
 * Working days between start and end inclusive, excluding Saturdays,
 * Sundays and public holidays. Dates are YYYY-MM-DD strings.
 */
export function workingDays(start: string, end: string, holidays: Set<string>): number {
  let days = 0;
  const cursor = new Date(`${start}T00:00:00Z`);
  const last = new Date(`${end}T00:00:00Z`);
  while (cursor.getTime() <= last.getTime()) {
    const dow = cursor.getUTCDay(); // 0 = Sunday, 6 = Saturday
    const iso = cursor.toISOString().slice(0, 10);
    if (dow !== 0 && dow !== 6 && !holidays.has(iso)) days++;
    cursor.setUTCDate(cursor.getUTCDate() + 1);
  }
  return days;
}

/**
 * Leave days for a request: working days minus 0.5 per half-day flag,
 * clamped to a minimum of 0.5. Returns 0 when the range contains no
 * working days at all (weekends / holidays only) so callers can reject it.
 */
export function computeLeaveDays(
  start: string,
  end: string,
  holidays: Set<string>,
  startHalf: boolean,
  endHalf: boolean
): number {
  const days = workingDays(start, end, holidays);
  if (days <= 0) return 0;
  let result = days;
  if (startHalf) result -= 0.5;
  if (endHalf) result -= 0.5;
  return Math.max(0.5, result);
}

export interface Balance {
  leaveType: LeaveTypeWithAccrual;
  /** Entitlement to date: accrual sum this year (monthly) or annual entitlement. */
  entitled: number;
  /** Days carried over into this year (expire at year-end). */
  carryOver: number;
  taken: number; // approved days this year
  pending: number; // pending days this year
  available: number; // entitled + carryOver - taken
}

/**
 * Single source of truth for a leave balance. For accrual_method='monthly'
 * types, entitled-to-date = SUM(leave_accruals for the year); for 'annual'
 * types, entitled = annual_entitlement_days. Carry-over for the year is
 * tracked separately and included in `available`.
 *
 * Pass `db` explicitly in tests (in-memory better-sqlite3); defaults to the
 * app database.
 */
export function getBalance(
  employeeId: number,
  leaveTypeId: number,
  year: number,
  db: DatabaseType.Database = getDb()
): Balance | null {
  const leaveType = db.prepare("SELECT * FROM leave_types WHERE id = ?").get(leaveTypeId) as
    | LeaveTypeWithAccrual
    | undefined;
  if (!leaveType) return null;

  let entitled: number;
  if (leaveType.accrual_method === "monthly") {
    entitled = (
      db
        .prepare(
          `SELECT COALESCE(SUM(days), 0) AS d FROM leave_accruals
           WHERE employee_id = ? AND leave_type_id = ? AND period LIKE ?`
        )
        .get(employeeId, leaveTypeId, `${year}-%`) as { d: number }
    ).d;
  } else {
    entitled = leaveType.annual_entitlement_days;
  }

  const carryOver = (
    db
      .prepare(
        `SELECT COALESCE(SUM(days), 0) AS d FROM leave_carry_overs
         WHERE employee_id = ? AND leave_type_id = ? AND year = ?`
      )
      .get(employeeId, leaveTypeId, year) as { d: number }
  ).d;

  const usage = db
    .prepare(
      `SELECT
         COALESCE(SUM(CASE WHEN status = 'approved' THEN days ELSE 0 END), 0) AS taken,
         COALESCE(SUM(CASE WHEN status = 'pending' THEN days ELSE 0 END), 0) AS pending
       FROM leave_requests
       WHERE employee_id = ? AND leave_type_id = ? AND strftime('%Y', start_date) = ?`
    )
    .get(employeeId, leaveTypeId, String(year)) as { taken: number; pending: number };

  return {
    leaveType,
    entitled,
    carryOver,
    taken: usage.taken,
    pending: usage.pending,
    available: entitled + carryOver - usage.taken,
  };
}

/** Balance per leave type for the given employee and year (by start_date year). */
export function getBalances(employeeId: number, year: number): Balance[] {
  const db = getDb();
  const types = db.prepare("SELECT id FROM leave_types ORDER BY id").all() as { id: number }[];
  return types
    .map((t) => getBalance(employeeId, t.id, year, db))
    .filter((b): b is Balance => b !== null);
}

export function statusBadgeClass(status: string): string {
  switch (status) {
    case "approved":
      return "badge-green";
    case "pending":
      return "badge-yellow";
    case "rejected":
      return "badge-red";
    default:
      return "badge-gray";
  }
}

export function formatDays(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}
