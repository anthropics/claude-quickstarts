import { NextRequest, NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";

export async function PATCH(
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

  let body: { name?: string; description?: string; department_id?: number | null };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const db = getDb();

  const existing = db
    .prepare("SELECT id FROM onboarding_templates WHERE id = ?")
    .get(templateId) as { id: number } | undefined;
  if (!existing) {
    return NextResponse.json({ error: "Template not found." }, { status: 404 });
  }

  const { name, description, department_id } = body;

  const fields: string[] = [];
  const values: (string | number | null)[] = [];

  if (name !== undefined) {
    if (!name.trim()) return NextResponse.json({ error: "name cannot be empty." }, { status: 400 });
    fields.push("name = ?");
    values.push(name.trim());
  }
  if (description !== undefined) {
    fields.push("description = ?");
    values.push(description?.trim() ?? null);
  }
  if (department_id !== undefined) {
    fields.push("department_id = ?");
    values.push(department_id ?? null);
  }

  if (fields.length === 0) {
    return NextResponse.json({ error: "No fields to update." }, { status: 400 });
  }

  values.push(templateId);
  db.prepare(`UPDATE onboarding_templates SET ${fields.join(", ")} WHERE id = ?`).run(...values);
  logAudit(user.id, "update", "onboarding_template", templateId, fields.join("; "));

  return NextResponse.json({ ok: true });
}
