import { NextRequest, NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";

export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const user = getCurrentUser();
  const taskId = Number(params.id);
  if (isNaN(taskId)) {
    return NextResponse.json({ error: "Invalid task id." }, { status: 400 });
  }

  let body: { status?: string; notes?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const { status, notes } = body;
  if (!status) {
    return NextResponse.json({ error: "status is required." }, { status: 400 });
  }

  const validStatuses = ["pending", "in_progress", "completed", "skipped"];
  if (!validStatuses.includes(status)) {
    return NextResponse.json({ error: `Invalid status. Must be one of: ${validStatuses.join(", ")}.` }, { status: 400 });
  }

  const db = getDb();

  const task = db
    .prepare(`
      SELECT t.id, t.instance_id, t.assignee_type, t.assigned_to_id,
             oi.employee_id,
             e.manager_id
      FROM onboarding_tasks t
      JOIN onboarding_instances oi ON oi.id = t.instance_id
      JOIN employees e ON e.id = oi.employee_id
      WHERE t.id = ?
    `)
    .get(taskId) as {
    id: number;
    instance_id: number;
    assignee_type: string;
    assigned_to_id: number | null;
    employee_id: number;
    manager_id: number | null;
  } | undefined;

  if (!task) {
    return NextResponse.json({ error: "Task not found." }, { status: 404 });
  }

  // Auth check
  const userIsHr = isHr(user);
  const userIsAssignee = task.assigned_to_id === user.id;
  const userIsManager = user.role === "manager" && task.manager_id === user.id;
  const userIsEmployee = task.employee_id === user.id;

  if (!userIsHr && !userIsAssignee && !userIsManager && !userIsEmployee) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const now = new Date().toISOString().replace("T", " ").slice(0, 19);
  const completedAt = status === "completed" ? now : null;

  db.prepare(`
    UPDATE onboarding_tasks
    SET status = ?, notes = ?, completed_at = ?
    WHERE id = ?
  `).run(status, notes?.trim() ?? null, completedAt, taskId);

  // Check if all tasks in the instance are completed or skipped
  const remaining = db
    .prepare(
      "SELECT COUNT(*) AS n FROM onboarding_tasks WHERE instance_id = ? AND status NOT IN ('completed', 'skipped')"
    )
    .get(task.instance_id) as { n: number };

  if (remaining.n === 0) {
    db.prepare("UPDATE onboarding_instances SET completed_at = ? WHERE id = ?").run(now, task.instance_id);
  } else {
    // Ensure instance is not marked completed if a task was un-completed
    db.prepare("UPDATE onboarding_instances SET completed_at = NULL WHERE id = ? AND completed_at IS NOT NULL").run(task.instance_id);
  }

  logAudit(user.id, "update", "onboarding_task", taskId, `status=${status}`);

  return NextResponse.json({ ok: true });
}
