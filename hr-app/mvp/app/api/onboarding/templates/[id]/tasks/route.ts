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

  const templateId = Number(params.id);
  if (isNaN(templateId)) {
    return NextResponse.json({ error: "Invalid template id." }, { status: 400 });
  }

  let body: {
    title?: string;
    description?: string;
    assignee_type?: string;
    due_offset_days?: number;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const { title, description, assignee_type, due_offset_days } = body;
  if (!title?.trim() || !assignee_type) {
    return NextResponse.json({ error: "title and assignee_type are required." }, { status: 400 });
  }

  const validTypes = ["hr", "it", "manager", "new_hire"];
  if (!validTypes.includes(assignee_type)) {
    return NextResponse.json({ error: `Invalid assignee_type. Must be one of: ${validTypes.join(", ")}.` }, { status: 400 });
  }

  const db = getDb();

  const template = db
    .prepare("SELECT id FROM onboarding_templates WHERE id = ?")
    .get(templateId) as { id: number } | undefined;
  if (!template) {
    return NextResponse.json({ error: "Template not found." }, { status: 404 });
  }

  const maxOrderRow = db
    .prepare("SELECT MAX(order_index) AS max_order FROM onboarding_template_tasks WHERE template_id = ?")
    .get(templateId) as { max_order: number | null };
  const nextOrder = (maxOrderRow.max_order ?? 0) + 1;

  const result = db
    .prepare(
      `INSERT INTO onboarding_template_tasks
         (template_id, title, description, assignee_type, due_offset_days, order_index)
       VALUES (?, ?, ?, ?, ?, ?)`
    )
    .run(
      templateId,
      title.trim(),
      description?.trim() ?? null,
      assignee_type,
      due_offset_days ?? 0,
      nextOrder
    );

  const id = Number(result.lastInsertRowid);
  logAudit(user.id, "create", "onboarding_template_task", id, `template_id=${templateId} title="${title}"`);

  return NextResponse.json({ id }, { status: 201 });
}
