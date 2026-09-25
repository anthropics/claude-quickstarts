import { NextRequest, NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const user = getCurrentUser();
  if (!isHr(user)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const instanceId = Number(params.id);
  if (isNaN(instanceId)) {
    return NextResponse.json({ error: "Invalid instance id." }, { status: 400 });
  }

  let body: {
    title?: string;
    description?: string;
    assignee_type?: string;
    assigned_to_id?: number | null;
    due_date?: string;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const { title, description, assignee_type, assigned_to_id, due_date } = body;
  if (!title || !assignee_type) {
    return NextResponse.json({ error: "title and assignee_type are required." }, { status: 400 });
  }

  const db = getDb();

  const instance = db
    .prepare("SELECT id FROM onboarding_instances WHERE id = ?")
    .get(instanceId) as { id: number } | undefined;
  if (!instance) {
    return NextResponse.json({ error: "Instance not found." }, { status: 404 });
  }

  const maxOrderRow = db
    .prepare("SELECT MAX(order_index) AS max_order FROM onboarding_tasks WHERE instance_id = ?")
    .get(instanceId) as { max_order: number | null };
  const nextOrder = (maxOrderRow.max_order ?? 0) + 1;

  const result = db
    .prepare(
      `INSERT INTO onboarding_tasks
         (instance_id, template_task_id, title, description, assignee_type, assigned_to_id, due_date, status, order_index)
       VALUES (?, NULL, ?, ?, ?, ?, ?, 'pending', ?)`
    )
    .run(
      instanceId,
      title.trim(),
      description?.trim() ?? null,
      assignee_type,
      assigned_to_id ?? null,
      due_date ?? null,
      nextOrder
    );

  const taskId = Number(result.lastInsertRowid);
  logAudit(user.id, "create", "onboarding_task", taskId, `ad-hoc instance_id=${instanceId} title="${title}"`);

  return NextResponse.json({ id: taskId }, { status: 201 });
}
