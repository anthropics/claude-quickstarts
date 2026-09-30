import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";

export async function POST(request: Request) {
  const user = getCurrentUser();
  if (!isHr(user)) {
    return NextResponse.json({ error: "Forbidden. HR/admin only." }, { status: 403 });
  }

  const db = getDb();

  let body: {
    title?: string;
    department_id?: number | null;
    location?: string;
    employment_type?: string;
    description?: string;
    requirements?: string;
    closes_at?: string;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const title = typeof body.title === "string" ? body.title.trim() : "";
  if (!title) {
    return NextResponse.json({ error: "Title is required." }, { status: 400 });
  }

  const validTypes = ["full_time", "part_time", "contract", "intern"];
  const employmentType = body.employment_type && validTypes.includes(body.employment_type)
    ? body.employment_type
    : "full_time";

  const result = db
    .prepare(
      `INSERT INTO job_postings (title, department_id, location, description, requirements, employment_type, status, created_by)
       VALUES (?, ?, ?, ?, ?, ?, 'draft', ?)`
    )
    .run(
      title,
      body.department_id ?? null,
      typeof body.location === "string" && body.location.trim() ? body.location.trim() : null,
      typeof body.description === "string" && body.description.trim() ? body.description.trim() : null,
      typeof body.requirements === "string" && body.requirements.trim() ? body.requirements.trim() : null,
      employmentType,
      user.id
    );

  const id = Number(result.lastInsertRowid);

  // Update closes_at separately (optional)
  if (typeof body.closes_at === "string" && body.closes_at.trim()) {
    db.prepare("UPDATE job_postings SET closes_at = ? WHERE id = ?").run(body.closes_at.trim(), id);
  }

  logAudit(user.id, "create", "job_posting", id, title);

  return NextResponse.json({ id }, { status: 201 });
}
