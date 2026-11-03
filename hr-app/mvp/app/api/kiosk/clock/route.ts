import { NextRequest, NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { hashPasswordSync, verifyPassword } from "@/lib/auth";
import {
  CLOCK_EVENT_TYPES,
  EVENT_LABELS,
  fmtTime,
  nowSql,
  todaySql,
  validateClockTransition,
  type ClockEventType,
} from "@/app/time/_lib/time";

export const dynamic = "force-dynamic";

const MAX_ATTEMPTS = 5;
const WINDOW_MINUTES = 15;

/** Constant-cost comparison target when the employee number is unknown. */
const DUMMY_PIN_HASH = hashPasswordSync("0000-dummy");

/**
 * Kiosk clock endpoint — public route, authenticated per action by
 * employee number + 4-digit PIN. Failures are generic ("Invalid credentials")
 * and rate-limited per employee number via login_attempts.
 */
export async function POST(req: NextRequest) {
  const body = (await req.json().catch(() => null)) as {
    employee_number?: string;
    pin?: string;
    type?: string;
  } | null;

  const employeeNumber = typeof body?.employee_number === "string" ? body.employee_number.trim().toUpperCase() : "";
  const pin = typeof body?.pin === "string" ? body.pin : "";
  const type = body?.type as ClockEventType | undefined;

  if (!employeeNumber || !pin) {
    return NextResponse.json({ error: "Employee number and PIN are required." }, { status: 400 });
  }
  if (!type || !CLOCK_EVENT_TYPES.includes(type)) {
    return NextResponse.json({ error: "Invalid clock event type." }, { status: 400 });
  }

  const db = getDb();
  const rateKey = `kiosk:${employeeNumber.toLowerCase()}`;
  const ip = req.headers.get("x-forwarded-for") ?? "local";

  const recentFailures = (
    db
      .prepare(
        `SELECT COUNT(*) AS n FROM login_attempts
         WHERE email = ? AND success = 0 AND attempted_at > datetime('now', ?)`
      )
      .get(rateKey, `-${WINDOW_MINUTES} minutes`) as { n: number }
  ).n;
  if (recentFailures >= MAX_ATTEMPTS) {
    return NextResponse.json(
      { error: `Too many failed attempts. Try again in ${WINDOW_MINUTES} minutes.` },
      { status: 429 }
    );
  }

  const employee = db
    .prepare(
      "SELECT id, first_name, pin_hash, status FROM employees WHERE upper(employee_number) = ?"
    )
    .get(employeeNumber) as { id: number; first_name: string; pin_hash: string | null; status: string } | undefined;

  // Verify against a dummy hash when unknown so timing does not reveal
  // whether the employee number or the PIN was wrong.
  const usable = employee && employee.pin_hash && employee.status === "active";
  const valid = (await verifyPassword(pin, usable ? employee.pin_hash! : DUMMY_PIN_HASH)) && Boolean(usable);

  db.prepare("INSERT INTO login_attempts (email, ip, success) VALUES (?, ?, ?)").run(rateKey, ip, valid ? 1 : 0);

  if (!valid || !employee) {
    return NextResponse.json({ error: "Invalid credentials" }, { status: 401 });
  }

  // Same state-machine validation as the main clock route.
  const todayEvents = db
    .prepare(
      "SELECT type, timestamp FROM clock_events WHERE employee_id = ? AND date(timestamp) = ? ORDER BY timestamp, id"
    )
    .all(employee.id, todaySql()) as { type: string; timestamp: string }[];

  const transitionError = validateClockTransition(todayEvents, type);
  if (transitionError) {
    return NextResponse.json({ error: transitionError }, { status: 400 });
  }

  const timestamp = nowSql();
  const result = db
    .prepare("INSERT INTO clock_events (employee_id, type, timestamp, method) VALUES (?, ?, ?, 'kiosk')")
    .run(employee.id, type, timestamp);
  logAudit(employee.id, `clock.${type}`, "clock_event", Number(result.lastInsertRowid), "kiosk");

  return NextResponse.json({
    ok: true,
    first_name: employee.first_name,
    time: fmtTime(timestamp),
    action: EVENT_LABELS[type].toLowerCase(),
  });
}
