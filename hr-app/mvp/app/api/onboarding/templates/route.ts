import { NextRequest, NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";

export async function POST(request: NextRequest) {
  const user = getCurrentUser();
  if (!isHr(user)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  let body: { name?: string; description?: string; department_id?: number | null };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const { name, description, department_id } = body;
  if (!name?.trim()) {
    return NextResponse.json({ error: "name is required." }, { status: 400 });
  }

  const db = getDb();
  const result = db
    .prepare("INSERT INTO onboarding_templates (name, description, department_id) VALUES (?, ?, ?)")
    .run(name.trim(), description?.trim() ?? null, department_id ?? null);

  const id = Number(result.lastInsertRowid);
  logAudit(user.id, "create", "onboarding_template", id, `name="${name}"`);

  return NextResponse.json({ id }, { status: 201 });
}
