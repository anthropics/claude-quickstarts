import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getApiUser, isHr } from "@/lib/session";
import { validateTemplatePayload } from "./_lib/validation";

export const dynamic = "force-dynamic";

/** Creates a letter template. Body: { name, type, body_template }. HR only. */
export async function POST(req: Request) {
  const user = getApiUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (!isHr(user)) return NextResponse.json({ error: "Forbidden" }, { status: 403 });

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const result = validateTemplatePayload(body);
  if ("error" in result) return NextResponse.json({ error: result.error }, { status: 400 });

  const res = getDb()
    .prepare("INSERT INTO letter_templates (name, type, body_template) VALUES (?, ?, ?)")
    .run(result.data.name, result.data.type, result.data.body_template);
  const id = Number(res.lastInsertRowid);

  logAudit(user.id, "letter_template.create", "letter_template", id, result.data.name);
  return NextResponse.json({ id }, { status: 201 });
}
