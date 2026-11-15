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

  const templateId = Number(params.id);
  const taskId = Number(params.taskId);
  if (isNaN(templateId) || isNaN(taskId)) {
    return NextResponse.json({ error: "Invalid id." }, { status: 400 });
  }

  const db = getDb();

  const task = db
    .prepare("SELECT id FROM onboarding_template_tasks WHERE id = ? AND template_id = ?")
    .get(taskId, templateId) as { id: number } | undefined;
  if (!task) {
    return NextResponse.json({ error: "Task not found." }, { status: 404 });
  }

  db.prepare("DELETE FROM onboarding_template_tasks WHERE id = ?").run(taskId);
  logAudit(user.id, "delete", "onboarding_template_task", taskId, `template_id=${templateId}`);

  return NextResponse.json({ ok: true });
}
