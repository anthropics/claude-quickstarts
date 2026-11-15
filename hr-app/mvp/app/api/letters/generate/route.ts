import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getApiUser, isHr } from "@/lib/session";
import { notify } from "@/lib/notify";
import { renderTemplate } from "@/app/letters/_lib/render";
import { mergeDataForEmployee, type LetterTemplate } from "@/app/letters/_lib/data";

export const dynamic = "force-dynamic";

/**
 * Renders a letter from a template for an employee.
 * Body: { template_id, employee_id, reason?, confirm? }
 * - confirm falsy  → returns { title, content } (preview only, nothing saved)
 * - confirm true   → saves to generated_letters, notifies the employee,
 *                    returns { id, title }
 */
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
  const input = (typeof body === "object" && body !== null ? body : {}) as Record<string, unknown>;

  const templateId = Number(input.template_id);
  const employeeId = Number(input.employee_id);
  if (!Number.isInteger(templateId) || templateId <= 0) {
    return NextResponse.json({ error: "template_id is required." }, { status: 400 });
  }
  if (!Number.isInteger(employeeId) || employeeId <= 0) {
    return NextResponse.json({ error: "employee_id is required." }, { status: 400 });
  }
  const reason = typeof input.reason === "string" ? input.reason.trim() : "";

  const db = getDb();
  const template = db.prepare("SELECT * FROM letter_templates WHERE id = ?").get(templateId) as
    | LetterTemplate
    | undefined;
  if (!template) return NextResponse.json({ error: "Template not found." }, { status: 404 });

  const data = mergeDataForEmployee(db, employeeId, user, reason);
  if (!data) return NextResponse.json({ error: "Employee not found." }, { status: 404 });

  const content = renderTemplate(template.body_template, data);
  const title = `${template.name} — ${data.first_name} ${data.last_name}`;

  if (!input.confirm) {
    return NextResponse.json({ title, content });
  }

  const res = db
    .prepare(
      "INSERT INTO generated_letters (employee_id, template_id, title, content, created_by) VALUES (?, ?, ?, ?, ?)"
    )
    .run(employeeId, templateId, title, content, user.id);
  const letterId = Number(res.lastInsertRowid);

  logAudit(user.id, "letter.generate", "generated_letter", letterId, title);
  notify({
    employeeId,
    type: "letter.issued",
    title: "A letter has been issued to you",
    body: title,
    link: `/letters/${letterId}`,
  });

  return NextResponse.json({ id: letterId, title }, { status: 201 });
}
