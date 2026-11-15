import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser } from "@/lib/session";
import { canTouchGoal } from "@/app/performance/_lib/perf";
import type { Employee, Goal } from "@/lib/types";

const GOAL_STATUSES = ["not_started", "in_progress", "at_risk", "achieved", "missed"];

export async function PATCH(request: Request, { params }: { params: { id: string } }) {
  const user = getCurrentUser();
  const db = getDb();

  const id = Number(params.id);
  if (!Number.isInteger(id)) {
    return NextResponse.json({ error: "Invalid goal id." }, { status: 400 });
  }

  let body: { current_value?: unknown; status?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const goal = db.prepare("SELECT * FROM goals WHERE id = ?").get(id) as Goal | undefined;
  if (!goal) {
    return NextResponse.json({ error: "Goal not found." }, { status: 404 });
  }

  const owner = db.prepare("SELECT * FROM employees WHERE id = ?").get(goal.employee_id) as
    | Employee
    | undefined;
  if (!canTouchGoal(user, goal.employee_id, owner?.manager_id ?? null)) {
    return NextResponse.json({ error: "You are not allowed to update this goal." }, { status: 403 });
  }

  const sets: string[] = [];
  const values: (number | string)[] = [];
  const detail: string[] = [];

  if (body.current_value !== undefined) {
    const currentValue = Number(body.current_value);
    if (!Number.isFinite(currentValue) || currentValue < 0) {
      return NextResponse.json({ error: "Current value must be a non-negative number." }, { status: 400 });
    }
    sets.push("current_value = ?");
    values.push(currentValue);
    detail.push(`current_value=${currentValue}`);
  }

  if (body.status !== undefined) {
    if (typeof body.status !== "string" || !GOAL_STATUSES.includes(body.status)) {
      return NextResponse.json({ error: "Invalid status." }, { status: 400 });
    }
    sets.push("status = ?");
    values.push(body.status);
    detail.push(`status=${body.status}`);
  }

  if (sets.length === 0) {
    return NextResponse.json({ error: "Nothing to update." }, { status: 400 });
  }

  sets.push("updated_at = datetime('now')");
  db.prepare(`UPDATE goals SET ${sets.join(", ")} WHERE id = ?`).run(...values, id);
  logAudit(user.id, "update", "goal", id, detail.join(", "));
  return NextResponse.json({ id });
}
