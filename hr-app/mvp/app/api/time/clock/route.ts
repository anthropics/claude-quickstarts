import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser } from "@/lib/session";
import {
  CLOCK_EVENT_TYPES,
  nowSql,
  todaySql,
  validateClockTransition,
  type ClockEventType,
} from "@/app/time/_lib/time";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const user = getCurrentUser();
  const body = (await req.json().catch(() => null)) as { type?: string } | null;
  const type = body?.type as ClockEventType | undefined;

  if (!type || !CLOCK_EVENT_TYPES.includes(type)) {
    return NextResponse.json({ error: "Invalid clock event type." }, { status: 400 });
  }

  const db = getDb();
  const todayEvents = db
    .prepare(
      "SELECT type, timestamp FROM clock_events WHERE employee_id = ? AND date(timestamp) = ? ORDER BY timestamp, id"
    )
    .all(user.id, todaySql()) as { type: string; timestamp: string }[];

  const transitionError = validateClockTransition(todayEvents, type);
  if (transitionError) {
    return NextResponse.json({ error: transitionError }, { status: 400 });
  }

  const result = db
    .prepare("INSERT INTO clock_events (employee_id, type, timestamp, method) VALUES (?, ?, ?, 'web')")
    .run(user.id, type, nowSql());
  logAudit(user.id, `clock.${type}`, "clock_event", Number(result.lastInsertRowid));

  return NextResponse.json({ ok: true });
}
