import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { BenefitElection } from "@/lib/types";

export async function PATCH(request: Request, { params }: { params: { id: string } }) {
  const user = getCurrentUser();
  const db = getDb();

  const id = Number(params.id);
  if (!Number.isInteger(id)) {
    return NextResponse.json({ error: "Invalid election id." }, { status: 400 });
  }

  let body: { action?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }
  if (body.action !== "end") {
    return NextResponse.json({ error: "Unknown action. Use 'end'." }, { status: 400 });
  }

  const election = db.prepare("SELECT * FROM benefit_elections WHERE id = ?").get(id) as BenefitElection | undefined;
  if (!election) {
    return NextResponse.json({ error: "Benefit election not found." }, { status: 404 });
  }
  if (election.employee_id !== user.id && !isHr(user)) {
    return NextResponse.json({ error: "You can only end your own benefit enrolments." }, { status: 403 });
  }
  if (election.status === "ended") {
    return NextResponse.json({ error: "This enrolment has already ended." }, { status: 400 });
  }

  db.prepare("UPDATE benefit_elections SET status = 'ended', ended_at = datetime('now') WHERE id = ?").run(id);
  logAudit(user.id, "end", "benefit_election", id, `employee ${election.employee_id}, tier ${election.tier_id}`);

  return NextResponse.json({ id, status: "ended" });
}
