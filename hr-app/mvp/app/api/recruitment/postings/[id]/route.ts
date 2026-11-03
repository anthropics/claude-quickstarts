import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import { generateSlug } from "@/app/api/careers/_lib/validate";
import type { JobPosting } from "@/lib/types";

export async function PATCH(request: Request, { params }: { params: { id: string } }) {
  const user = getCurrentUser();
  if (!isHr(user)) {
    return NextResponse.json({ error: "Forbidden. HR/admin only." }, { status: 403 });
  }

  const db = getDb();
  const id = Number(params.id);
  if (!Number.isInteger(id) || id <= 0) {
    return NextResponse.json({ error: "Invalid posting id." }, { status: 400 });
  }

  const posting = db.prepare("SELECT * FROM job_postings WHERE id = ?").get(id) as
    | (JobPosting & { public_slug: string | null })
    | undefined;
  if (!posting) {
    return NextResponse.json({ error: "Job posting not found." }, { status: 404 });
  }

  let body: {
    title?: string;
    department_id?: number | null;
    location?: string;
    employment_type?: string;
    description?: string;
    requirements?: string;
    closes_at?: string | null;
    status?: string;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  // Status transitions
  if (body.status !== undefined) {
    const validStatuses = ["draft", "open", "closed", "on_hold"];
    if (!validStatuses.includes(body.status)) {
      return NextResponse.json({ error: "Invalid status value." }, { status: 400 });
    }
    const validTransitions: Record<string, string[]> = {
      draft: ["open"],
      open: ["closed", "on_hold"],
      on_hold: ["open", "closed"],
      closed: [],
    };
    if (!validTransitions[posting.status]?.includes(body.status)) {
      return NextResponse.json(
        { error: `Cannot transition from '${posting.status}' to '${body.status}'.` },
        { status: 400 }
      );
    }
    if (body.status === "open") {
      // Publishing: stamp posted_at and mint the public careers slug if empty.
      const slug = posting.public_slug?.trim()
        ? posting.public_slug
        : generateSlug(body.title?.trim() || posting.title, id);
      db.prepare(
        `UPDATE job_postings SET status = ?, posted_at = datetime('now'), public_slug = ? WHERE id = ?`
      ).run(body.status, slug, id);
    } else {
      db.prepare("UPDATE job_postings SET status = ? WHERE id = ?").run(body.status, id);
    }
    logAudit(user.id, "status_change", "job_posting", id, `${posting.status} → ${body.status}`);
  }

  // Field updates (if provided)
  const updates: string[] = [];
  const args: (string | number | null)[] = [];

  const validTypes = ["full_time", "part_time", "contract", "intern"];

  if (typeof body.title === "string" && body.title.trim()) {
    updates.push("title = ?");
    args.push(body.title.trim());
  }
  if (body.department_id !== undefined) {
    updates.push("department_id = ?");
    args.push(body.department_id ?? null);
  }
  if (typeof body.location === "string") {
    updates.push("location = ?");
    args.push(body.location.trim() || null);
  }
  if (typeof body.employment_type === "string" && validTypes.includes(body.employment_type)) {
    updates.push("employment_type = ?");
    args.push(body.employment_type);
  }
  if (typeof body.description === "string") {
    updates.push("description = ?");
    args.push(body.description.trim() || null);
  }
  if (typeof body.requirements === "string") {
    updates.push("requirements = ?");
    args.push(body.requirements.trim() || null);
  }
  if (body.closes_at !== undefined) {
    updates.push("closes_at = ?");
    args.push(typeof body.closes_at === "string" && body.closes_at.trim() ? body.closes_at.trim() : null);
  }

  if (updates.length > 0) {
    args.push(id);
    db.prepare(`UPDATE job_postings SET ${updates.join(", ")} WHERE id = ?`).run(...args);
    logAudit(user.id, "update", "job_posting", id, updates.join(", "));
  }

  return NextResponse.json({ id, ok: true });
}
