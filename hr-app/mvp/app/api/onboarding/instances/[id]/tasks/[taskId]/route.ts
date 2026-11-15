import { NextRequest, NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";

export async function DELETE(
  _request: NextRequest,
  { params }: { params: { id: string; taskId: string } }
) {
  const user = getCurrentUser();
  if (!isHr(user)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const instanceId = Number(params.id);
  const taskId = Number(params.taskId);
  if (isNaN(instanceId) || isNaN(taskId)) {
    return NextResponse.json({ error: "Invalid id." }, { status: 400 });
  }

  const db = getDb();

  const task = db
    .prepare("SELECT id, status, instance_id FROM onboarding_tasks WHERE id = ? AND instance_id = ?")
    .get(taskId, instanceId) as { id: number; status: string; instance_id: number } | undefined;
  if (!task) {
    return NextResponse.json({ error: "Task not found." }, { status: 404 });
  }

  if (task.status !== "pending") {
    return NextResponse.json({ error: "Only pending tasks can be deleted." }, { status: 400 });
  }

  db.prepare("DELETE FROM onboarding_tasks WHERE id = ?").run(taskId);
  logAudit(user.id, "delete", "onboarding_task", taskId, `instance_id=${instanceId}`);

  return NextResponse.json({ ok: true });
}
