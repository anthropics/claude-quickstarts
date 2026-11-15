import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import { generateReviewPairs } from "./_lib/generate";

const CYCLE_TYPES = ["annual", "biannual", "quarterly", "probation"];
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export async function POST(request: Request) {
  const user = getCurrentUser();
  const db = getDb();

  if (!isHr(user)) {
    return NextResponse.json({ error: "Only HR can create review cycles." }, { status: 403 });
  }

  let body: {
    name?: unknown;
    type?: unknown;
    period_start?: unknown;
    period_end?: unknown;
    launch?: unknown;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const name = typeof body.name === "string" ? body.name.trim() : "";
  if (!name) {
    return NextResponse.json({ error: "Name is required." }, { status: 400 });
  }
  const type = typeof body.type === "string" && CYCLE_TYPES.includes(body.type) ? body.type : "annual";

  const periodStart = typeof body.period_start === "string" && DATE_RE.test(body.period_start) ? body.period_start : null;
  const periodEnd = typeof body.period_end === "string" && DATE_RE.test(body.period_end) ? body.period_end : null;
  if (!periodStart || !periodEnd) {
    return NextResponse.json({ error: "Valid period start and end dates are required." }, { status: 400 });
  }
  if (periodEnd < periodStart) {
    return NextResponse.json({ error: "Period end must be on or after period start." }, { status: 400 });
  }

  const launch = Boolean(body.launch);

  const result = db
    .prepare("INSERT INTO review_cycles (name, type, period_start, period_end, status) VALUES (?, ?, ?, ?, ?)")
    .run(name, type, periodStart, periodEnd, launch ? "active" : "setup");
  const id = Number(result.lastInsertRowid);

  let reviewsCreated = 0;
  if (launch) {
    reviewsCreated = generateReviewPairs(db, id);
  }

  logAudit(user.id, "create", "review_cycle", id, launch ? `launched with ${reviewsCreated} reviews` : name);
  return NextResponse.json({ id, reviews_created: reviewsCreated }, { status: 201 });
}
