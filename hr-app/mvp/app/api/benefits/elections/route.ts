import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { BenefitPlan, BenefitTier } from "@/lib/types";

export async function POST(request: Request) {
  const user = getCurrentUser();
  const db = getDb();

  let body: { tier_id?: number; employee_id?: number };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const tierId = Number(body.tier_id);
  if (!Number.isInteger(tierId)) {
    return NextResponse.json({ error: "tier_id is required." }, { status: 400 });
  }

  const tier = db.prepare("SELECT * FROM benefit_tiers WHERE id = ?").get(tierId) as BenefitTier | undefined;
  if (!tier) {
    return NextResponse.json({ error: "Benefit tier not found." }, { status: 404 });
  }
  const plan = db.prepare("SELECT * FROM benefit_plans WHERE id = ?").get(tier.plan_id) as BenefitPlan;
  if (plan.active !== 1) {
    return NextResponse.json({ error: "This plan is no longer active." }, { status: 400 });
  }

  // employee_id is only honoured for HR/admin; everyone else enrols themselves.
  let employeeId = user.id;
  if (body.employee_id !== undefined && isHr(user)) {
    const targetId = Number(body.employee_id);
    if (!Number.isInteger(targetId)) {
      return NextResponse.json({ error: "Invalid employee_id." }, { status: 400 });
    }
    const target = db.prepare("SELECT id FROM employees WHERE id = ?").get(targetId) as { id: number } | undefined;
    if (!target) {
      return NextResponse.json({ error: "Employee not found." }, { status: 404 });
    }
    employeeId = target.id;
  }

  const alreadyOnTier = db
    .prepare("SELECT id FROM benefit_elections WHERE employee_id = ? AND tier_id = ? AND status = 'active'")
    .get(employeeId, tierId) as { id: number } | undefined;
  if (alreadyOnTier) {
    return NextResponse.json({ error: "Already enrolled in this tier." }, { status: 400 });
  }

  let electionId = 0;
  let switched = false;
  db.transaction(() => {
    // One active election per plan: end any active election on another tier of this plan.
    const ended = db
      .prepare(
        `UPDATE benefit_elections
         SET status = 'ended', ended_at = datetime('now')
         WHERE employee_id = ? AND status = 'active'
           AND tier_id IN (SELECT id FROM benefit_tiers WHERE plan_id = ?)`
      )
      .run(employeeId, tier.plan_id);
    switched = ended.changes > 0;

    // A previous (ended) election on this exact tier may exist — reactivate it to
    // respect the UNIQUE(employee_id, tier_id) constraint.
    const prior = db
      .prepare("SELECT id FROM benefit_elections WHERE employee_id = ? AND tier_id = ?")
      .get(employeeId, tierId) as { id: number } | undefined;
    if (prior) {
      db.prepare(
        "UPDATE benefit_elections SET status = 'active', effective_from = date('now'), ended_at = NULL WHERE id = ?"
      ).run(prior.id);
      electionId = prior.id;
    } else {
      const result = db
        .prepare(
          "INSERT INTO benefit_elections (employee_id, tier_id, status, effective_from) VALUES (?, ?, 'active', date('now'))"
        )
        .run(employeeId, tierId);
      electionId = Number(result.lastInsertRowid);
    }
  })();

  logAudit(
    user.id,
    "enrol",
    "benefit_election",
    electionId,
    `${plan.name} / ${tier.name} for employee ${employeeId}${switched ? " (previous tier ended)" : ""}`
  );

  return NextResponse.json({ id: electionId, status: "active" }, { status: 201 });
}
