import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getApiUser, isHr } from "@/lib/session";

export const dynamic = "force-dynamic";

const CATEGORIES = ["contract", "id_document", "certificate", "policy", "other"];

/**
 * Attaches an already-uploaded file (POST /api/files) to an employee's
 * document vault. Body: { file_id, title, category }.
 * Access: HR always; an employee may attach documents to their OWN profile.
 */
export async function POST(req: Request, { params }: { params: { id: string } }) {
  const user = getApiUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const employeeId = Number(params.id);
  if (!Number.isInteger(employeeId) || employeeId <= 0) {
    return NextResponse.json({ error: "Invalid employee id." }, { status: 400 });
  }
  if (!isHr(user) && user.id !== employeeId) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const db = getDb();
  const employee = db.prepare("SELECT id FROM employees WHERE id = ?").get(employeeId);
  if (!employee) return NextResponse.json({ error: "Employee not found." }, { status: 404 });

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }
  const input = (typeof body === "object" && body !== null ? body : {}) as Record<string, unknown>;

  const fileId = Number(input.file_id);
  if (!Number.isInteger(fileId) || fileId <= 0) {
    return NextResponse.json({ error: "file_id is required." }, { status: 400 });
  }
  const title = typeof input.title === "string" ? input.title.trim() : "";
  if (!title) return NextResponse.json({ error: "title is required." }, { status: 400 });
  if (title.length > 200) {
    return NextResponse.json({ error: "title must be 200 characters or fewer." }, { status: 400 });
  }
  const category = typeof input.category === "string" ? input.category : "";
  if (!CATEGORIES.includes(category)) {
    return NextResponse.json({ error: `category must be one of: ${CATEGORIES.join(", ")}.` }, { status: 400 });
  }

  const file = db.prepare("SELECT id, uploaded_by FROM files WHERE id = ?").get(fileId) as
    | { id: number; uploaded_by: number | null }
    | undefined;
  if (!file) return NextResponse.json({ error: "File not found." }, { status: 404 });
  // Non-HR users may only link files they uploaded themselves — otherwise a
  // guessed file id would let them expose someone else's upload on their vault.
  if (!isHr(user) && file.uploaded_by !== user.id) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const res = db
    .prepare(
      "INSERT INTO employee_documents (employee_id, file_id, category, title, uploaded_by) VALUES (?, ?, ?, ?, ?)"
    )
    .run(employeeId, fileId, category, title, user.id);
  const docId = Number(res.lastInsertRowid);

  logAudit(user.id, "employee_document.create", "employee_document", docId, `${title} (${category})`);
  return NextResponse.json({ id: docId }, { status: 201 });
}
