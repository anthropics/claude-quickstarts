import { NextRequest, NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { saveUpload, UploadError } from "@/lib/uploads";
import { notify } from "@/lib/notify";
import type { JobPosting } from "@/lib/types";
import { validateApplication } from "../_lib/validate";

export const dynamic = "force-dynamic";

/**
 * Public (unauthenticated) application endpoint for the careers site.
 * Multipart form: first_name, last_name, email, phone?, cv (file, required),
 * slug (posting public_slug), website (honeypot — must be empty).
 */
export async function POST(req: NextRequest) {
  const form = await req.formData().catch(() => null);
  if (!form) {
    return NextResponse.json({ error: "Expected multipart form data." }, { status: 400 });
  }

  const validation = validateApplication({
    first_name: form.get("first_name"),
    last_name: form.get("last_name"),
    email: form.get("email"),
    phone: form.get("phone"),
    website: form.get("website"),
  });
  if (!validation.ok) {
    return NextResponse.json({ error: validation.error }, { status: 400 });
  }
  const { first_name, last_name, email, phone } = validation.data;

  const slug = typeof form.get("slug") === "string" ? (form.get("slug") as string).trim() : "";
  const db = getDb();
  const posting = slug
    ? (db
        .prepare("SELECT * FROM job_postings WHERE public_slug = ? AND status = 'open'")
        .get(slug) as JobPosting | undefined)
    : undefined;
  if (!posting) {
    return NextResponse.json(
      { error: "This position is no longer accepting applications." },
      { status: 404 }
    );
  }

  // Dedupe: same email already applied to this posting.
  const existing = db
    .prepare(
      `SELECT a.id FROM applications a
       JOIN candidates c ON c.id = a.candidate_id
       WHERE a.job_posting_id = ? AND lower(c.email) = ?`
    )
    .get(posting.id, email);
  if (existing) {
    return NextResponse.json({ error: "You have already applied for this position." }, { status: 409 });
  }

  const cv = form.get("cv");
  if (!cv || typeof cv === "string" || cv.size === 0) {
    return NextResponse.json({ error: "A CV file is required." }, { status: 400 });
  }

  let cvFileId: number;
  try {
    const buffer = Buffer.from(await cv.arrayBuffer());
    const stored = saveUpload(buffer, cv.name, cv.type, null);
    cvFileId = stored.id;
  } catch (e) {
    if (e instanceof UploadError) {
      return NextResponse.json({ error: e.message }, { status: 400 });
    }
    throw e;
  }

  const { candidateId, appId } = db.transaction(() => {
    const candidateResult = db
      .prepare(
        `INSERT INTO candidates (first_name, last_name, email, phone, cv_filename, cv_file_id, source)
         VALUES (?, ?, ?, ?, ?, ?, 'careers')`
      )
      .run(first_name, last_name, email, phone, cv.name.slice(0, 255), cvFileId);
    const candidateId = Number(candidateResult.lastInsertRowid);

    const appResult = db
      .prepare("INSERT INTO applications (job_posting_id, candidate_id, stage) VALUES (?, ?, 'applied')")
      .run(posting.id, candidateId);
    const appId = Number(appResult.lastInsertRowid);

    return { candidateId, appId };
  })();

  logAudit(null, "create", "candidate", candidateId, `${first_name} ${last_name} applied via careers site`);
  logAudit(null, "create", "application", appId, `candidate ${candidateId} → job ${posting.id} (careers)`);

  // Notify the posting's creator and all HR/admins (deduplicated).
  const hrIds = (
    db
      .prepare("SELECT id FROM employees WHERE role IN ('hr', 'admin') AND status = 'active'")
      .all() as { id: number }[]
  ).map((r) => r.id);
  const recipients = new Set<number>(hrIds);
  if (posting.created_by) {
    const creator = db
      .prepare("SELECT id FROM employees WHERE id = ? AND status = 'active'")
      .get(posting.created_by) as { id: number } | undefined;
    if (creator) recipients.add(creator.id);
  }
  for (const employeeId of Array.from(recipients)) {
    notify({
      employeeId,
      type: "recruitment.application",
      title: `New application for ${posting.title}`,
      body: `${first_name} ${last_name} applied via the careers site.`,
      link: `/recruitment/${posting.id}/applications/${appId}`,
    });
  }

  return NextResponse.json({ ok: true, application_id: appId }, { status: 201 });
}
