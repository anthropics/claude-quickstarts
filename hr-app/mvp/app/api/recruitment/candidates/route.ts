import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { JobPosting } from "@/lib/types";

export async function POST(request: Request) {
  const user = getCurrentUser();
  if (!isHr(user)) {
    return NextResponse.json({ error: "Forbidden. HR/admin only." }, { status: 403 });
  }

  const db = getDb();

  let body: {
    first_name?: string;
    last_name?: string;
    email?: string;
    phone?: string;
    cv_filename?: string;
    cv_file_id?: number | null;
    source?: string;
    job_posting_id?: number;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const first_name = typeof body.first_name === "string" ? body.first_name.trim() : "";
  const last_name = typeof body.last_name === "string" ? body.last_name.trim() : "";
  const email = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";

  if (!first_name || !last_name) {
    return NextResponse.json({ error: "First and last name are required." }, { status: 400 });
  }
  if (!email) {
    return NextResponse.json({ error: "Email is required." }, { status: 400 });
  }
  if (!body.job_posting_id) {
    return NextResponse.json({ error: "job_posting_id is required." }, { status: 400 });
  }

  const posting = db.prepare("SELECT * FROM job_postings WHERE id = ?").get(body.job_posting_id) as JobPosting | undefined;
  if (!posting) {
    return NextResponse.json({ error: "Job posting not found." }, { status: 404 });
  }

  const validSources = ["direct", "linkedin", "indeed", "referral", "internal"];
  const source = body.source && validSources.includes(body.source) ? body.source : "direct";

  // Optional uploaded CV (file id from POST /api/files).
  let cvFileId: number | null = null;
  let cvFilename: string | null =
    typeof body.cv_filename === "string" && body.cv_filename.trim() ? body.cv_filename.trim() : null;
  if (body.cv_file_id !== undefined && body.cv_file_id !== null) {
    if (typeof body.cv_file_id !== "number" || !Number.isInteger(body.cv_file_id)) {
      return NextResponse.json({ error: "cv_file_id must be an integer." }, { status: 400 });
    }
    const file = db.prepare("SELECT id, original_name FROM files WHERE id = ?").get(body.cv_file_id) as
      | { id: number; original_name: string }
      | undefined;
    if (!file) {
      return NextResponse.json({ error: "Uploaded CV file not found." }, { status: 400 });
    }
    cvFileId = file.id;
    cvFilename = cvFilename ?? file.original_name;
  }

  const candidateResult = db
    .prepare(
      `INSERT INTO candidates (first_name, last_name, email, phone, cv_filename, cv_file_id, source)
       VALUES (?, ?, ?, ?, ?, ?, ?)`
    )
    .run(
      first_name,
      last_name,
      email,
      typeof body.phone === "string" && body.phone.trim() ? body.phone.trim() : null,
      cvFilename,
      cvFileId,
      source
    );

  const candidateId = Number(candidateResult.lastInsertRowid);

  // Check if application already exists
  const existing = db
    .prepare("SELECT id FROM applications WHERE job_posting_id = ? AND candidate_id = ?")
    .get(body.job_posting_id, candidateId);
  if (existing) {
    return NextResponse.json({ error: "This candidate already has an application for this posting." }, { status: 400 });
  }

  const appResult = db
    .prepare(
      `INSERT INTO applications (job_posting_id, candidate_id, stage) VALUES (?, ?, 'applied')`
    )
    .run(body.job_posting_id, candidateId);

  const appId = Number(appResult.lastInsertRowid);
  logAudit(user.id, "create", "candidate", candidateId, `${first_name} ${last_name} for job ${body.job_posting_id}`);
  logAudit(user.id, "create", "application", appId, `candidate ${candidateId} → job ${body.job_posting_id}`);

  return NextResponse.json({ candidateId, appId }, { status: 201 });
}
