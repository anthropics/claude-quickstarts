import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getApiUser, isHr } from "@/lib/session";
import { validateTemplatePayload } from "../_lib/validation";

export const dynamic = "force-dynamic";

/** Updates a letter template. Body: { name, type, body_template }. HR only. */
export async function PATCH(req: Request, { params }: { params: { id: string } }) {
  const user = getApiUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (!isHr(user)) return NextResponse.json({ error: "Forbidden" }, { status: 403 });

  const id = Number(params.id);
  if (!Number.isInteger(id) || id <= 0) {
    return NextResponse.json({ error: "Invalid template id." }, { status: 400 });
  }

  const db = getDb();
  const existing = db.prepare("SELECT id FROM letter_templates WHERE id = ?").get(id);
  if (!existing) return NextResponse.json({ error: "Template not found." }, { status: 404 });

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const result = validateTemplatePayload(body);
  if ("error" in result) return NextResponse.json({ error: result.error }, { status: 400 });

  db.prepare("UPDATE letter_templates SET name = ?, type = ?, body_template = ? WHERE id = ?").run(
    result.data.name,
    result.data.type,
    result.data.body_template,
    id
  );

  logAudit(user.id, "letter_template.update", "letter_template", id, result.data.name);
  return NextResponse.json({ id });
}
