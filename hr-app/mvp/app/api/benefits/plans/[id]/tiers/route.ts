import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { BenefitPlan } from "@/lib/types";

export async function POST(request: Request, { params }: { params: { id: string } }) {
  const user = getCurrentUser();
  if (!isHr(user)) {
    return NextResponse.json({ error: "Only HR and admins can add benefit tiers." }, { status: 403 });
  }
  const db = getDb();

  const planId = Number(params.id);
  if (!Number.isInteger(planId)) {
    return NextResponse.json({ error: "Invalid plan id." }, { status: 400 });
  }
  const plan = db.prepare("SELECT * FROM benefit_plans WHERE id = ?").get(planId) as BenefitPlan | undefined;
  if (!plan) {
    return NextResponse.json({ error: "Benefit plan not found." }, { status: 404 });
  }

  let body: {
    name?: string;
    monthly_cost_employee?: number;
    monthly_cost_employer?: number;
    description?: string;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const name = typeof body.name === "string" ? body.name.trim() : "";
  if (!name) {
    return NextResponse.json({ error: "Tier name is required." }, { status: 400 });
  }
  const costEmployee = Number(body.monthly_cost_employee ?? 0);
  const costEmployer = Number(body.monthly_cost_employer ?? 0);
  if (!Number.isFinite(costEmployee) || costEmployee < 0 || !Number.isFinite(costEmployer) || costEmployer < 0) {
    return NextResponse.json({ error: "Monthly costs must be zero or positive numbers." }, { status: 400 });
  }
  const description =
    typeof body.description === "string" && body.description.trim() ? body.description.trim() : null;

  const result = db
    .prepare(
      `INSERT INTO benefit_tiers (plan_id, name, monthly_cost_employee, monthly_cost_employer, description)
       VALUES (?, ?, ?, ?, ?)`
    )
    .run(planId, name, costEmployee, costEmployer, description);

  const id = Number(result.lastInsertRowid);
  logAudit(user.id, "create", "benefit_tier", id, `${plan.name} / ${name}`);

  return NextResponse.json({ id }, { status: 201 });
}
