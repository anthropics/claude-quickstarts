import { NextResponse } from "next/server";
import { getDb, logAudit } from "@/lib/db";
import { getCurrentUser, isHr } from "@/lib/session";
import type { BenefitPlan } from "@/lib/types";
import { isBenefitCategory } from "@/app/benefits/_lib/benefits";

export async function PATCH(request: Request, { params }: { params: { id: string } }) {
  const user = getCurrentUser();
  if (!isHr(user)) {
    return NextResponse.json({ error: "Only HR and admins can update benefit plans." }, { status: 403 });
  }
  const db = getDb();

  const id = Number(params.id);
  if (!Number.isInteger(id)) {
    return NextResponse.json({ error: "Invalid plan id." }, { status: 400 });
  }
  const plan = db.prepare("SELECT * FROM benefit_plans WHERE id = ?").get(id) as BenefitPlan | undefined;
  if (!plan) {
    return NextResponse.json({ error: "Benefit plan not found." }, { status: 404 });
  }

  let body: {
    name?: string;
    category?: string;
    provider?: string | null;
    description?: string | null;
    active?: boolean | number;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const updates: string[] = [];
  const values: (string | number | null)[] = [];

  if (body.name !== undefined) {
    const name = typeof body.name === "string" ? body.name.trim() : "";
    if (!name) {
      return NextResponse.json({ error: "Plan name cannot be empty." }, { status: 400 });
    }
    updates.push("name = ?");
    values.push(name);
  }
  if (body.category !== undefined) {
    if (!isBenefitCategory(body.category)) {
      return NextResponse.json(
        { error: "Category must be one of: medical, retirement, life, disability, wellness." },
        { status: 400 }
      );
    }
    updates.push("category = ?");
    values.push(body.category);
  }
  if (body.provider !== undefined) {
    updates.push("provider = ?");
    values.push(typeof body.provider === "string" && body.provider.trim() ? body.provider.trim() : null);
  }
  if (body.description !== undefined) {
    updates.push("description = ?");
    values.push(typeof body.description === "string" && body.description.trim() ? body.description.trim() : null);
  }
  if (body.active !== undefined) {
    updates.push("active = ?");
    values.push(body.active ? 1 : 0);
  }

  if (updates.length === 0) {
    return NextResponse.json({ error: "No valid fields to update." }, { status: 400 });
  }

  db.prepare(`UPDATE benefit_plans SET ${updates.join(", ")} WHERE id = ?`).run(...values, id);
  logAudit(user.id, "update", "benefit_plan", id, updates.map((u) => u.split(" ")[0]).join(", "));

  const updated = db.prepare("SELECT * FROM benefit_plans WHERE id = ?").get(id) as BenefitPlan;
  return NextResponse.json(updated);
}
