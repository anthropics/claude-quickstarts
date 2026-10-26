import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser } from "@/lib/session";
import type { Review } from "@/lib/types";

export async function PATCH(request: Request, { params }: { params: { id: string } }) {
  const user = getCurrentUser();
  const db = getDb();

  const id = Number(params.id);
  if (!Number.isInteger(id)) {
    return NextResponse.json({ error: "Invalid review id." }, { status: 400 });
  }

  let body: {
    action?: unknown;
    strengths?: unknown;
    improvements?: unknown;
    overall_comments?: unknown;
    rating?: unknown;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const review = db.prepare("SELECT * FROM reviews WHERE id = ?").get(id) as Review | undefined;
  if (!review) {
    return NextResponse.json({ error: "Review not found." }, { status: 404 });
  }
  if (review.reviewer_id !== user.id) {
    return NextResponse.json({ error: "Only the assigned reviewer can edit this review." }, { status: 403 });
  }
  if (review.status === "submitted" || review.status === "acknowledged") {
    return NextResponse.json({ error: "This review has already been submitted." }, { status: 400 });
  }

  const action = body.action === "submit" ? "submit" : "save";

  const asText = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v.trim() : null);
  const strengths = body.strengths !== undefined ? asText(body.strengths) : review.strengths;
  const improvements = body.improvements !== undefined ? asText(body.improvements) : review.improvements;
  const overallComments =
    body.overall_comments !== undefined ? asText(body.overall_comments) : review.overall_comments;

  let rating: number | null = review.rating;
  if (body.rating !== undefined) {
    if (body.rating === null || body.rating === "") {
      rating = null;
    } else {
      const r = Number(body.rating);
      if (!Number.isInteger(r) || r < 1 || r > 5) {
        return NextResponse.json({ error: "Rating must be an integer between 1 and 5." }, { status: 400 });
      }
      rating = r;
    }
  }

  if (action === "submit" && rating === null) {
    return NextResponse.json({ error: "A rating is required to submit the review." }, { status: 400 });
  }

  if (action === "submit") {
    db.prepare(
      `UPDATE reviews
       SET strengths = ?, improvements = ?, overall_comments = ?, rating = ?,
           status = 'submitted', submitted_at = datetime('now')
       WHERE id = ?`
    ).run(strengths, improvements, overallComments, rating, id);
    logAudit(user.id, "submit", "review", id, `${review.type} review for employee ${review.employee_id}`);
    return NextResponse.json({ id, status: "submitted" });
  }

  db.prepare(
    `UPDATE reviews
     SET strengths = ?, improvements = ?, overall_comments = ?, rating = ?, status = 'in_progress'
     WHERE id = ?`
  ).run(strengths, improvements, overallComments, rating, id);
  logAudit(user.id, "save_draft", "review", id);
  return NextResponse.json({ id, status: "in_progress" });
}
