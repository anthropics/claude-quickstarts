import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { ReviewCycle } from "@/lib/types";
import { generateReviewPairs } from "../_lib/generate";

export async function PATCH(request: Request, { params }: { params: { id: string } }) {
  const user = getCurrentUser();
  const db = getDb();

  if (!isHr(user)) {
    return NextResponse.json({ error: "Only HR can manage review cycles." }, { status: 403 });
  }

  const id = Number(params.id);
  if (!Number.isInteger(id)) {
    return NextResponse.json({ error: "Invalid cycle id." }, { status: 400 });
  }

  let body: { action?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const cycle = db.prepare("SELECT * FROM review_cycles WHERE id = ?").get(id) as ReviewCycle | undefined;
  if (!cycle) {
    return NextResponse.json({ error: "Review cycle not found." }, { status: 404 });
  }

  if (body.action === "activate") {
    if (cycle.status !== "setup") {
      return NextResponse.json({ error: "Only cycles in setup can be activated." }, { status: 400 });
    }
    db.prepare("UPDATE review_cycles SET status = 'active' WHERE id = ?").run(id);
    const created = generateReviewPairs(db, id);
    logAudit(user.id, "activate", "review_cycle", id, `${created} reviews generated`);
    return NextResponse.json({ id, status: "active", reviews_created: created });
  }

  if (body.action === "close") {
    if (cycle.status !== "active") {
      return NextResponse.json({ error: "Only active cycles can be closed." }, { status: 400 });
    }
    db.prepare("UPDATE review_cycles SET status = 'closed' WHERE id = ?").run(id);
    logAudit(user.id, "close", "review_cycle", id);
    return NextResponse.json({ id, status: "closed" });
  }

  return NextResponse.json({ error: "Unknown action. Use 'activate' or 'close'." }, { status: 400 });
}
