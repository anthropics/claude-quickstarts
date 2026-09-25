import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, canManage, isHr } from "@/lib/session";
import type { Employee } from "@/lib/types";

/** Normalise "2026-07-10T14:30" (datetime-local) to "2026-07-10 14:30:00". */
function normaliseDateTime(value: string): string | null {
  const v = value.trim().replace("T", " ");
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(v)) return `${v}:00`;
  if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(v)) return v;
  return null;
}

export async function POST(request: Request) {
  const user = getCurrentUser();
  const db = getDb();

  if (!canManage(user)) {
    return NextResponse.json({ error: "Only managers or HR can schedule 1-on-1s." }, { status: 403 });
  }

  let body: { employee_id?: unknown; scheduled_at?: unknown; agenda?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const employeeId = Number(body.employee_id);
  if (!Number.isInteger(employeeId)) {
    return NextResponse.json({ error: "Invalid employee id." }, { status: 400 });
  }
  if (employeeId === user.id) {
    return NextResponse.json({ error: "You cannot schedule a 1-on-1 with yourself." }, { status: 400 });
  }

  const employee = db.prepare("SELECT * FROM employees WHERE id = ?").get(employeeId) as
    | Employee
    | undefined;
  if (!employee) {
    return NextResponse.json({ error: "Employee not found." }, { status: 404 });
  }
  if (!isHr(user) && employee.manager_id !== user.id) {
    return NextResponse.json(
      { error: "You can only schedule 1-on-1s with your direct reports." },
      { status: 403 }
    );
  }

  const scheduledAt =
    typeof body.scheduled_at === "string" ? normaliseDateTime(body.scheduled_at) : null;
  if (!scheduledAt) {
    return NextResponse.json({ error: "A valid date and time is required." }, { status: 400 });
  }

  const agenda = typeof body.agenda === "string" && body.agenda.trim() ? body.agenda.trim() : null;

  const result = db
    .prepare(
      `INSERT INTO one_on_ones (manager_id, employee_id, scheduled_at, agenda, status)
       VALUES (?, ?, ?, ?, 'scheduled')`
    )
    .run(user.id, employeeId, scheduledAt, agenda);

  const id = Number(result.lastInsertRowid);
  logAudit(user.id, "create", "one_on_one", id, `with employee ${employeeId} at ${scheduledAt}`);
  return NextResponse.json({ id }, { status: 201 });
}
