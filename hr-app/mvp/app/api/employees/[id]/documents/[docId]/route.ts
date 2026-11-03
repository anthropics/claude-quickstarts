import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getApiUser, isHr } from "@/lib/session";

export const dynamic = "force-dynamic";

/** Removes a document from an employee's vault. HR only. */
export async function DELETE(_req: Request, { params }: { params: { id: string; docId: string } }) {
  const user = getApiUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  if (!isHr(user)) return NextResponse.json({ error: "Forbidden" }, { status: 403 });

  const employeeId = Number(params.id);
  const docId = Number(params.docId);
  if (!Number.isInteger(employeeId) || employeeId <= 0 || !Number.isInteger(docId) || docId <= 0) {
    return NextResponse.json({ error: "Invalid id." }, { status: 400 });
  }

  const db = getDb();
  const doc = db
    .prepare("SELECT id, title FROM employee_documents WHERE id = ? AND employee_id = ?")
    .get(docId, employeeId) as { id: number; title: string } | undefined;
  if (!doc) return NextResponse.json({ error: "Document not found." }, { status: 404 });

  db.prepare("DELETE FROM employee_documents WHERE id = ?").run(docId);
  logAudit(user.id, "employee_document.delete", "employee_document", docId, doc.title);
  return NextResponse.json({ ok: true });
}
