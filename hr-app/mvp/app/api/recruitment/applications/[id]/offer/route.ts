import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { Application } from "@/lib/types";

export async function POST(request: Request, { params }: { params: { id: string } }) {
  const user = getCurrentUser();
  if (!isHr(user)) {
    return NextResponse.json({ error: "Forbidden. HR/admin only." }, { status: 403 });
  }

  const db = getDb();
  const id = Number(params.id);
  if (!Number.isInteger(id) || id <= 0) {
    return NextResponse.json({ error: "Invalid application id." }, { status: 400 });
  }

  const app = db.prepare("SELECT * FROM applications WHERE id = ?").get(id) as Application | undefined;
  if (!app) {
    return NextResponse.json({ error: "Application not found." }, { status: 404 });
  }

  let body: {
    salary?: number;
    start_date?: string;
    expiry_date?: string;
    notes?: string;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  if (typeof body.salary !== "number" || body.salary <= 0) {
    return NextResponse.json({ error: "A positive salary is required." }, { status: 400 });
  }
  if (typeof body.start_date !== "string" || !body.start_date.trim()) {
    return NextResponse.json({ error: "start_date is required." }, { status: 400 });
  }
  if (typeof body.expiry_date !== "string" || !body.expiry_date.trim()) {
    return NextResponse.json({ error: "expiry_date is required." }, { status: 400 });
  }

  const result = db
    .prepare(
      `INSERT INTO offers (application_id, salary, start_date, expiry_date, status, notes)
       VALUES (?, ?, ?, ?, 'draft', ?)`
    )
    .run(
      id,
      body.salary,
      body.start_date.trim(),
      body.expiry_date.trim(),
      typeof body.notes === "string" && body.notes.trim() ? body.notes.trim() : null
    );

  const offerId = Number(result.lastInsertRowid);

  // Advance application stage to 'offer' if not already there or further
  const stagesAfterOffer = ["offer", "hired", "rejected", "withdrawn"];
  if (!stagesAfterOffer.includes(app.stage)) {
    db.prepare(`UPDATE applications SET stage = 'offer', updated_at = datetime('now') WHERE id = ?`).run(id);
    logAudit(user.id, "stage_change", "application", id, `${app.stage} → offer`);
  }

  logAudit(user.id, "create", "offer", offerId, `app ${id} salary ${body.salary}`);

  return NextResponse.json({ id: offerId }, { status: 201 });
}
